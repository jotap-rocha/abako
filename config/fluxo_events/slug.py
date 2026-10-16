"""Deriva slug sintético ``dev-loop-*`` a partir de ``PROMPT_*.md``."""

from __future__ import annotations

import re
from pathlib import Path

_NON_ALNUM = re.compile(r"[^a-z0-9]+")
_MULTI_DASH = re.compile(r"-{2,}")


def slug_from_prompt_path(path: Path | str) -> str:
    """``PROMPT_FOO_BAR.md`` → ``dev-loop-foo-bar`` (lower, kebab, ``[a-z0-9-]``).

    Regras:
    - stem do path; strip prefixo ``PROMPT_`` / ``PROMPT`` (case-insensitive)
    - lower; não alfanumérico → ``-``; colapsar ``--``; strip ``-``
    - prefixo fixo ``dev-loop-``
    """
    stem = Path(path).stem
    upper = stem.upper()
    if upper.startswith("PROMPT_"):
        raw = stem[len("PROMPT_") :]
    elif upper.startswith("PROMPT"):
        raw = stem[len("PROMPT") :].lstrip("_")
    else:
        raw = stem
    name = raw.lower()
    name = _NON_ALNUM.sub("-", name)
    name = _MULTI_DASH.sub("-", name).strip("-")
    if not name:
        return "dev-loop"
    return f"dev-loop-{name}"
