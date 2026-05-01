import logging
import os
import shutil
import site
import subprocess
import sys
import threading
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path


def _add_cuda_dll_directories() -> None:
    if sys.platform != "win32":
        return
    site_dirs = site.getsitepackages() + [site.getusersitepackages()]
    subdirs = (
        "nvidia/cublas/bin",
        "nvidia/cudnn/bin",
        "nvidia/cuda_nvrtc/bin",
        "nvidia/cuda_runtime/bin",
    )
    found: list[str] = []
    for sp in site_dirs:
        for sub in subdirs:
            p = Path(sp) / sub
            if p.is_dir():
                os.add_dll_directory(str(p))
                found.append(str(p))
    if found:
        os.environ["PATH"] = os.pathsep.join(found) + os.pathsep + os.environ.get("PATH", "")


_add_cuda_dll_directories()

from faster_whisper import WhisperModel  # noqa: E402  (must follow DLL setup)

from . import storage, summarize as summarizer
from .config import settings
from .schemas import JobStatus, Segment

logger = logging.getLogger(__name__)

_model_lock = threading.Lock()
_model: WhisperModel | None = None
_executor = ThreadPoolExecutor(max_workers=1, thread_name_prefix="whisper-worker")


def get_model() -> WhisperModel:
    global _model
    with _model_lock:
        if _model is None:
            logger.info(
                "Loading WhisperModel size=%s device=%s compute_type=%s",
                settings.model_size,
                settings.device,
                settings.compute_type,
            )
            _model = WhisperModel(
                settings.model_size,
                device=settings.device,
                compute_type=settings.compute_type,
            )
    return _model


def submit(job_id: str, audio_path: Path, template_id: str | None = None) -> None:
    _executor.submit(_run, job_id, audio_path, template_id)


def _normalize_to_wav(src: Path) -> Path:
    if src.suffix.lower() == ".wav":
        return src
    ffmpeg = shutil.which("ffmpeg")
    if ffmpeg is None:
        logger.warning("ffmpeg not found; passing %s as-is to faster-whisper", src.name)
        return src
    dst = src.with_name("audio.normalized.wav")
    proc = subprocess.run(
        [
            ffmpeg, "-y", "-loglevel", "error",
            "-i", str(src),
            "-ac", "1", "-ar", "16000", "-c:a", "pcm_s16le",
            str(dst),
        ],
        capture_output=True,
    )
    if proc.returncode != 0:
        stderr = proc.stderr.decode("utf-8", errors="replace").strip()
        raise RuntimeError(f"ffmpeg failed to normalize audio: {stderr}")
    return dst


def _run(job_id: str, audio_path: Path, template_id: str | None = None) -> None:
    try:
        storage.update_meta(job_id, status=JobStatus.running)
        meta = storage.read_meta(job_id)
        assert meta is not None
        decode_path = _normalize_to_wav(audio_path)
        model = get_model()
        segments_iter, info = model.transcribe(
            str(decode_path),
            language=meta.language,
            vad_filter=True,
            beam_size=5,
            initial_prompt=settings.initial_prompt,
        )
        segments: list[Segment] = []
        text_lines: list[str] = []
        prev_end: float | None = None
        for seg in segments_iter:
            segments.append(Segment(start=seg.start, end=seg.end, text=seg.text))
            text = seg.text.strip()
            if not text:
                continue
            if (
                prev_end is not None
                and seg.start - prev_end >= settings.paragraph_gap_seconds
            ):
                text_lines.append("")
            text_lines.append(text)
            prev_end = seg.end
        full_text = "\n".join(text_lines).strip()
        storage.write_transcript(job_id, full_text, segments)
        if settings.summary_enabled and full_text:
            storage.update_meta(
                job_id,
                status=JobStatus.summarizing,
                detected_language=info.language,
                duration_seconds=info.duration,
            )
            try:
                summary_text = summarizer.summarize(full_text, template_id=template_id)
                storage.write_summary(job_id, summary_text)
            except Exception as exc:
                logger.exception("Summarization failed for job %s", job_id)
                storage.update_meta(job_id, summary_error=str(exc))
            storage.update_meta(job_id, status=JobStatus.completed)
        else:
            storage.update_meta(
                job_id,
                status=JobStatus.completed,
                detected_language=info.language,
                duration_seconds=info.duration,
            )
    except Exception as exc:
        logger.exception("Transcription failed for job %s", job_id)
        storage.update_meta(job_id, status=JobStatus.failed, error=str(exc))
