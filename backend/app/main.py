import logging
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import PlainTextResponse

from . import storage, transcribe
from .config import CORS_ORIGINS, settings
from .schemas import JobDetail, JobMeta

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(_: FastAPI):
    n = storage.fail_orphaned_jobs("server restarted while job was in progress")
    if n:
        logger.info("Marked %d orphaned job(s) as failed on startup", n)
    yield


app = FastAPI(title="whisper-api", version="0.1.0", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/health")
def health() -> dict:
    return {
        "status": "ok",
        "model_size": settings.model_size,
        "device": settings.device,
        "compute_type": settings.compute_type,
        "summary_enabled": settings.summary_enabled,
        "ollama_model": settings.ollama_model if settings.summary_enabled else None,
    }


@app.post("/jobs", response_model=JobMeta)
async def create_job(
    audio: UploadFile = File(...),
    language: str | None = Form(default=None),
) -> JobMeta:
    if audio.filename is None:
        raise HTTPException(status_code=400, detail="audio file required")
    suffix = Path(audio.filename).suffix or ".bin"
    lang = language or settings.default_language
    meta = storage.create_job(
        audio_filename=audio.filename,
        model=settings.model_size,
        language=lang,
    )
    dest = storage.audio_path(meta.id, suffix)
    with dest.open("wb") as f:
        while chunk := await audio.read(1024 * 1024):
            f.write(chunk)
    transcribe.submit(meta.id, dest)
    return meta


@app.get("/jobs", response_model=list[JobMeta])
def list_jobs() -> list[JobMeta]:
    return storage.list_jobs()


@app.get("/jobs/{job_id}", response_model=JobDetail)
def get_job(job_id: str) -> JobDetail:
    meta = storage.read_meta(job_id)
    if meta is None:
        raise HTTPException(status_code=404, detail="job not found")
    text, segments = storage.read_transcript(job_id)
    summary = storage.read_summary(job_id)
    return JobDetail(
        **meta.model_dump(),
        text=text,
        segments=segments,
        summary=summary,
    )


@app.get("/jobs/{job_id}/transcript", response_class=PlainTextResponse)
def get_transcript(job_id: str) -> str:
    text, _ = storage.read_transcript(job_id)
    if text is None:
        raise HTTPException(status_code=404, detail="transcript not ready")
    return text


@app.get("/jobs/{job_id}/summary", response_class=PlainTextResponse)
def get_summary(job_id: str) -> str:
    summary = storage.read_summary(job_id)
    if summary is None:
        raise HTTPException(status_code=404, detail="summary not ready")
    return summary
