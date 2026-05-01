from datetime import datetime
from enum import Enum

from pydantic import BaseModel


class JobStatus(str, Enum):
    pending = "pending"
    running = "running"
    summarizing = "summarizing"
    completed = "completed"
    failed = "failed"


class Segment(BaseModel):
    start: float
    end: float
    text: str


class JobMeta(BaseModel):
    id: str
    status: JobStatus
    created_at: datetime
    updated_at: datetime
    audio_filename: str
    model: str
    language: str | None = None
    detected_language: str | None = None
    duration_seconds: float | None = None
    error: str | None = None
    summary_error: str | None = None
    template_id: str | None = None


class JobDetail(JobMeta):
    text: str | None = None
    segments: list[Segment] | None = None
    summary: str | None = None
