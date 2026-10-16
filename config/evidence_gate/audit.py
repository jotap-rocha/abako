"""Audit append-only — ``evidencias/audit.jsonl``."""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path


@dataclass(frozen=True, slots=True)
class AuditEvent:
    """Evento de collect (sem PII/secrets)."""

    timestamp: str
    task_id: str
    criterion_id: str
    exit_code: int
    log_path: str
    command_summary: str
    collect_ok: bool
    invalid_cap: bool = False


def audit_path(root: Path, audit_file: str = "audit.jsonl") -> Path:
    return root / audit_file


def append_audit_event(root: Path, event: AuditEvent, audit_file: str = "audit.jsonl") -> Path:
    """Append 1 linha JSON — nunca reescreve o arquivo inteiro."""
    path = audit_path(root, audit_file)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(asdict(event), ensure_ascii=False) + "\n")
    return path


def read_audit_events(root: Path, audit_file: str = "audit.jsonl") -> list[AuditEvent]:
    path = audit_path(root, audit_file)
    if not path.is_file():
        return []
    events: list[AuditEvent] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        data = json.loads(line)
        events.append(
            AuditEvent(
                timestamp=str(data["timestamp"]),
                task_id=str(data["task_id"]),
                criterion_id=str(data["criterion_id"]),
                exit_code=int(data["exit_code"]),
                log_path=str(data["log_path"]),
                command_summary=str(data["command_summary"]),
                collect_ok=bool(data["collect_ok"]),
                invalid_cap=bool(data.get("invalid_cap", False)),
            )
        )
    return events


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def summarize_command(command: str, max_len: int = 120) -> str:
    compact = " ".join(command.split())
    if len(compact) <= max_len:
        return compact
    return compact[: max_len - 3] + "..."
