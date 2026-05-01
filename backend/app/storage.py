import json
import uuid
from datetime import datetime, timezone
from pathlib import Path

from .config import settings
from .schemas import JobMeta, JobStatus, Segment


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _job_dir(job_id: str) -> Path:
    return settings.data_dir / "jobs" / job_id


def create_job(
    audio_filename: str,
    model: str,
    language: str | None,
    template_id: str | None = None,
) -> JobMeta:
    job_id = uuid.uuid4().hex
    _job_dir(job_id).mkdir(parents=True, exist_ok=False)
    meta = JobMeta(
        id=job_id,
        status=JobStatus.pending,
        created_at=_now(),
        updated_at=_now(),
        audio_filename=audio_filename,
        model=model,
        language=language,
        template_id=template_id,
    )
    write_meta(meta)
    return meta


def write_meta(meta: JobMeta) -> None:
    p = _job_dir(meta.id) / "meta.json"
    p.write_text(meta.model_dump_json(indent=2), encoding="utf-8")


def read_meta(job_id: str) -> JobMeta | None:
    p = _job_dir(job_id) / "meta.json"
    if not p.exists():
        return None
    return JobMeta.model_validate_json(p.read_text(encoding="utf-8"))


def update_meta(job_id: str, **fields) -> JobMeta:
    meta = read_meta(job_id)
    if meta is None:
        raise FileNotFoundError(job_id)
    data = meta.model_dump()
    data.update(fields)
    data["updated_at"] = _now()
    new_meta = JobMeta.model_validate(data)
    write_meta(new_meta)
    return new_meta


def audio_path(job_id: str, suffix: str) -> Path:
    return _job_dir(job_id) / f"audio{suffix}"


def transcript_path(job_id: str) -> Path:
    return _job_dir(job_id) / "transcript.txt"


def segments_path(job_id: str) -> Path:
    return _job_dir(job_id) / "segments.json"


def summary_path(job_id: str) -> Path:
    return _job_dir(job_id) / "summary.txt"


def write_transcript(job_id: str, text: str, segments: list[Segment]) -> None:
    transcript_path(job_id).write_text(text, encoding="utf-8")
    segments_path(job_id).write_text(
        json.dumps(
            [s.model_dump() for s in segments],
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )


def read_transcript(job_id: str) -> tuple[str | None, list[Segment] | None]:
    tp = transcript_path(job_id)
    sp = segments_path(job_id)
    if not tp.exists():
        return None, None
    text = tp.read_text(encoding="utf-8")
    segments: list[Segment] | None = None
    if sp.exists():
        raw = json.loads(sp.read_text(encoding="utf-8"))
        segments = [Segment.model_validate(s) for s in raw]
    return text, segments


def write_summary(job_id: str, text: str) -> None:
    summary_path(job_id).write_text(text, encoding="utf-8")


def read_summary(job_id: str) -> str | None:
    p = summary_path(job_id)
    if not p.exists():
        return None
    return p.read_text(encoding="utf-8")


def list_jobs() -> list[JobMeta]:
    base = settings.data_dir / "jobs"
    if not base.exists():
        return []
    out: list[JobMeta] = []
    for d in base.iterdir():
        if d.is_dir():
            m = read_meta(d.name)
            if m is not None:
                out.append(m)
    out.sort(key=lambda m: m.created_at, reverse=True)
    return out


def fail_orphaned_jobs(message: str) -> int:
    in_progress = (JobStatus.pending, JobStatus.running, JobStatus.summarizing)
    count = 0
    for meta in list_jobs():
        if meta.status in in_progress:
            update_meta(meta.id, status=JobStatus.failed, error=message)
            count += 1
    return count
