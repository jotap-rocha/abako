"""Stack local fail-soft para herança de parent_event_id (sem mutex)."""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

from config.fluxo_events.paths import fluxo_dir_for_slug

STACK_FILENAME = "stack.json"


def stack_path(projetos_root: Path, slug: str) -> Path:
    """Path ``{projetos}/{slug}/fluxo/stack.json``."""
    return fluxo_dir_for_slug(projetos_root, slug) / STACK_FILENAME


def peek_parent(projetos_root: Path, slug: str) -> tuple[str | None, str | None]:
    """Retorna o topo da stack (event_id do pai) ou ``None`` se vazia/erro."""
    try:
        items = _read_stack(stack_path(projetos_root, slug))
        if not items:
            return None, None
        top = items[-1]
        if isinstance(top, str) and top.strip():
            return top.strip(), None
        return None, None
    except OSError as exc:
        msg = f"stack peek FS soft: {exc}"
        _warn(msg)
        return None, msg
    except Exception as exc:  # noqa: BLE001 — fail-soft
        msg = f"stack peek soft: {exc}"
        _warn(msg)
        return None, msg


def push_event(projetos_root: Path, slug: str, event_id: str) -> str | None:
    """Empilha ``event_id``; retorna warning soft ou ``None``."""
    if not event_id or not str(event_id).strip():
        return None
    path = stack_path(projetos_root, slug)
    try:
        items = _read_stack(path)
        items.append(str(event_id).strip())
        _write_stack(path, items)
        return None
    except OSError as exc:
        msg = f"stack push FS soft: {exc}"
        _warn(msg)
        return msg
    except Exception as exc:  # noqa: BLE001
        msg = f"stack push soft: {exc}"
        _warn(msg)
        return msg


def pop_event(projetos_root: Path, slug: str) -> str | None:
    """Remove o topo da stack; fail-soft."""
    path = stack_path(projetos_root, slug)
    try:
        items = _read_stack(path)
        if items:
            items.pop()
        _write_stack(path, items)
        return None
    except OSError as exc:
        msg = f"stack pop FS soft: {exc}"
        _warn(msg)
        return msg
    except Exception as exc:  # noqa: BLE001
        msg = f"stack pop soft: {exc}"
        _warn(msg)
        return msg


def _read_stack(path: Path) -> list[Any]:
    if not path.is_file():
        return []
    raw = path.read_text(encoding="utf-8").strip()
    if not raw:
        return []
    data = json.loads(raw)
    if isinstance(data, list):
        return list(data)
    if isinstance(data, dict) and isinstance(data.get("stack"), list):
        return list(data["stack"])
    return []


def _write_stack(path: Path, items: list[Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(items, ensure_ascii=False, separators=(",", ":")),
        encoding="utf-8",
    )


def _warn(message: str) -> None:
    print(f"[fluxo-events] WARN: {message}", file=sys.stderr)
