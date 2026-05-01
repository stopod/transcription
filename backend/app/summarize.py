import logging

import httpx

from . import templates as templates_mod
from .config import settings

logger = logging.getLogger(__name__)


def _resolve_prompt(template_id: str | None) -> tuple[str, str | None]:
    if template_id:
        tpl = templates_mod.get_template(template_id)
        if tpl is not None:
            return tpl.prompt, tpl.id
        logger.warning(
            "Template %r not found; falling back to default summary_prompt",
            template_id,
        )
    return settings.summary_prompt, None


def summarize(transcript: str, template_id: str | None = None) -> str:
    prompt_text, resolved = _resolve_prompt(template_id)
    payload = {
        "model": settings.ollama_model,
        "prompt": f"{prompt_text}\n\n---\n{transcript}\n---",
        "stream": False,
        "options": {"temperature": 0.3},
    }
    logger.info(
        "Requesting summary from Ollama: model=%s url=%s template=%s transcript_chars=%d",
        settings.ollama_model,
        settings.ollama_url,
        resolved or "<default>",
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
