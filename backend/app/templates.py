from __future__ import annotations

import logging
import re
from pathlib import Path

from pydantic import BaseModel

from .config import settings

logger = logging.getLogger(__name__)

_ID_RE = re.compile(r"^[A-Za-z0-9_\-]+$")
_FRONTMATTER_RE = re.compile(r"\A---\s*\n(.*?)\n---\s*\n?", re.DOTALL)


class Template(BaseModel):
    id: str
    name: str
    description: str | None = None
    prompt: str


def _templates_dir() -> Path:
    return settings.data_dir / "templates"


def _parse_frontmatter(text: str) -> tuple[dict[str, str], str]:
    m = _FRONTMATTER_RE.match(text)
    if not m:
        return {}, text
    meta_block = m.group(1)
    body = text[m.end():]
    meta: dict[str, str] = {}
    for line in meta_block.splitlines():
        line = line.strip()
        if not line or line.startswith("#") or ":" not in line:
            continue
        key, _, value = line.partition(":")
        meta[key.strip()] = value.strip().strip('"').strip("'")
    return meta, body


def _load_one(path: Path) -> Template | None:
    tid = path.stem
    if not _ID_RE.match(tid):
        logger.warning("Skipping template with invalid id: %s", path.name)
        return None
    try:
        text = path.read_text(encoding="utf-8")
    except OSError as exc:
        logger.warning("Failed to read template %s: %s", path.name, exc)
        return None
    meta, body = _parse_frontmatter(text)
    prompt = body.strip()
    if not prompt:
        logger.warning("Skipping template with empty body: %s", path.name)
        return None
    return Template(
        id=tid,
        name=meta.get("name", tid),
        description=meta.get("description") or None,
        prompt=prompt,
    )


def list_templates() -> list[Template]:
    d = _templates_dir()
    if not d.exists():
        return []
    out: list[Template] = []
    for p in sorted(d.glob("*.md")):
        t = _load_one(p)
        if t is not None:
            out.append(t)
    return out


def get_template(template_id: str) -> Template | None:
    if not _ID_RE.match(template_id):
        return None
    p = _templates_dir() / f"{template_id}.md"
    if not p.exists():
        return None
    return _load_one(p)
