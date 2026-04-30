import logging

import httpx

from .config import settings

logger = logging.getLogger(__name__)


def summarize(transcript: str) -> str:
    payload = {
        "model": settings.ollama_model,
        "prompt": f"{settings.summary_prompt}\n\n---\n{transcript}\n---",
        "stream": False,
        "options": {"temperature": 0.3},
    }
    logger.info(
        "Requesting summary from Ollama: model=%s url=%s transcript_chars=%d",
        settings.ollama_model,
        settings.ollama_url,
        len(transcript),
    )
    with httpx.Client(timeout=settings.ollama_timeout_seconds) as client:
        res = client.post(f"{settings.ollama_url}/api/generate", json=payload)
        res.raise_for_status()
        data = res.json()
    text = (data.get("response") or "").strip()
    if not text:
        raise RuntimeError("Ollama returned empty response")
    return text
