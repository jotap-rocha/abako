"""Rotate keep-tail quando events.jsonl excede o cap (G3-a)."""

from __future__ import annotations

import sys
from pathlib import Path


def append_with_rotate(
    path: Path,
    line: str,
    *,
    max_bytes: int,
) -> str | None:
    """Appenda uma linha; se estourar o cap, mantém o tail e avisa (soft).

    Sem lock (G2-a). Retorna warning ou ``None``.
    """
    path.parent.mkdir(parents=True, exist_ok=True)
    text = line.rstrip("\n") + "\n"
    with path.open("a", encoding="utf-8") as handle:
        handle.write(text)

    size = path.stat().st_size
    if size <= max_bytes:
        return None

    warning = (
        f"events.jsonl excedeu {max_bytes} bytes ({size}); "
        "rotate keep-tail aplicado (soft)"
    )
    _warn(warning)
    rotate_keep_tail(path, max_bytes=max_bytes)
    return warning


def rotate_keep_tail(path: Path, *, max_bytes: int) -> None:
    """Reescreve o arquivo mantendo o maior sufixo de linhas ≤ max_bytes."""
    if not path.is_file():
        return
    raw = path.read_bytes()
    if len(raw) <= max_bytes:
        return
    # Mantém o maior sufixo que cabe no cap, preferindo fronteira de linha.
    tail = raw[-max_bytes:]
    nl = tail.find(b"\n")
    if nl != -1 and nl + 1 < len(tail):
        tail = tail[nl + 1 :]
    path.write_bytes(tail)


def _warn(message: str) -> None:
    print(f"[fluxo-events] WARN: {message}", file=sys.stderr)
