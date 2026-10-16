"""Emit de eventos metadados (JSONL) — fail-soft, sem lock, sem PII."""

from __future__ import annotations

import json
import re
import sys
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping

from config.fluxo_events.contract import FluxoEventsContract
from config.fluxo_events.paths import (
    events_path,
    fluxo_dir_for_slug,
    load_contract_or_default,
    resolve_projetos_root,
)

REPO_ROOT = Path(__file__).resolve().parents[2]

ALLOWED_KEYS: frozenset[str] = frozenset(
    {
        "event_type",
        "ts",
        "phase",
        "agent",
        "task_id",
        "slug",
        "source",
        "event_id",
        "run_id",
        "parent_event_id",
    }
)

FORBIDDEN_KEY_PATTERNS: tuple[re.Pattern[str], ...] = (
    re.compile(r"prompt", re.I),
    re.compile(r"message", re.I),
    re.compile(r"content", re.I),
    re.compile(r"diff", re.I),
    re.compile(r"secret", re.I),
    re.compile(r"password", re.I),
    re.compile(r"token", re.I),
    re.compile(r"api[_-]?key", re.I),
    re.compile(r"cpf", re.I),
    re.compile(r"email", re.I),
    re.compile(r"telefone|phone", re.I),
    re.compile(r"connection.?string", re.I),
)

PHASE_SLUGS: dict[str, int] = {
    "IDEIA": 0,
    "REQUISITOS": 1,
    "PRD_HARNESS": 2,
    "IMPLEMENTAR": 3,
    "ENCERRAR": 4,
}

DEV_LOOP_PHASE_SLUGS: dict[str, int] = {
    "LOAD": 0,
    "VALIDATE": 1,
    "INIT_PICK": 2,
    "EXECUTE_VERIFY": 3,
    "UPDATE_CHECK": 4,
    "LOOP_LOG": 5,
    "SYNC": 6,
}


@dataclass(frozen=True, slots=True)
class EmitResult:
    """Resultado fail-soft de um emit."""

    ok: bool
    soft: bool
    warning: str | None
    line: str | None
    events_file: Path | None
    rendered: bool = False
    event_id: str | None = None
    run_id: str | None = None


def parse_emit_line(line: str | None) -> tuple[str | None, str | None]:
    """Extrai ``event_id`` e ``run_id`` de uma linha JSONL emitida."""
    if not line:
        return None, None
    try:
        payload = json.loads(line)
    except json.JSONDecodeError:
        return None, None
    if not isinstance(payload, dict):
        return None, None
    event_id = payload.get("event_id")
    run_id = payload.get("run_id")
    eid = str(event_id).strip() if isinstance(event_id, str) and event_id.strip() else None
    rid = str(run_id).strip() if isinstance(run_id, str) and run_id.strip() else None
    return eid, rid


def emit_event(
    *,
    slug: str,
    event_type: str,
    agent: str,
    phase: int | str,
    task_id: str | None = None,
    source: str | None = None,
    ts: str | None = None,
    event_id: str | None = None,
    run_id: str | None = None,
    parent_event_id: str | None = None,
    extra: Mapping[str, Any] | None = None,
    contract_path: Path | None = None,
    projetos_root: Path | None = None,
    repo_root: Path | None = None,
    auto_render: bool = True,
    mirror_cursor: bool = False,
) -> EmitResult:
    """Valida metadados, appenda 1 linha JSONL e opcionalmente dispara render.

    Fail-soft: erros de FS / validação retornam ``EmitResult(ok=False, soft=True)``
    sem levantar exceção que bloqueie o caller SDD.

    IDs causais (aditivos, version 1): ``event_id`` e ``run_id`` UUID v4 gerados se
    omitidos; ``parent_event_id`` explícito ou resolvido via stack (task 76).
    """
    root = repo_root or REPO_ROOT
    try:
        contract = load_contract_or_default(contract_path, repo_root=root)
        proj_root = resolve_projetos_root(projetos_root, repo_root=root)
        payload, strip_warn = _build_payload(
            contract=contract,
            slug=slug,
            event_type=event_type,
            agent=agent,
            phase=phase,
            task_id=task_id,
            source=source,
            ts=ts,
            event_id=event_id,
            run_id=run_id,
            parent_event_id=parent_event_id,
            extra=extra,
            projetos_root=proj_root,
        )
        if payload is None:
            return _soft_fail(strip_warn or "payload rejeitado (metadados inválidos)")

        line = json.dumps(payload, ensure_ascii=False, separators=(",", ":"))
        target = events_path(proj_root, slug, paths=contract.paths)
        _ensure_fluxo_dir(proj_root, slug)
        from config.fluxo_events.rotate import append_with_rotate  # noqa: PLC0415

        rotate_warn = append_with_rotate(
            target,
            line,
            max_bytes=contract.limits.max_events_bytes,
        )
        warning = _join_warnings(strip_warn, rotate_warn)

        rendered = False
        if auto_render:
            from config.fluxo_events.render import render_live  # noqa: PLC0415

            render_result = render_live(
                slug=slug,
                contract_path=contract_path,
                projetos_root=proj_root,
                repo_root=root,
            )
            rendered = render_result.ok
            if not render_result.ok and render_result.warning:
                warning = _join_warnings(warning, render_result.warning)

        if mirror_cursor:
            _mirror_best_effort(root, slug, line, contract, auto_render)

        event_id, run_id = parse_emit_line(line)
        return EmitResult(
            ok=True,
            soft=False,
            warning=warning,
            line=line,
            events_file=target,
            rendered=rendered,
            event_id=event_id,
            run_id=run_id,
        )
    except OSError as exc:
        return _soft_fail(f"emit FS error: {exc}")
    except Exception as exc:  # noqa: BLE001 — boundary fail-soft
        return _soft_fail(f"emit failed: {exc}")



def _build_payload(
    *,
    contract: FluxoEventsContract,
    slug: str,
    event_type: str,
    agent: str,
    phase: int | str,
    task_id: str | None,
    source: str | None,
    ts: str | None,
    event_id: str | None,
    run_id: str | None,
    parent_event_id: str | None,
    extra: Mapping[str, Any] | None,
    projetos_root: Path | None = None,
) -> tuple[dict[str, Any] | None, str | None]:
    warnings: list[str] = []
    if event_type not in contract.event_types:
        return None, f"event_type inválido: {event_type}"
    max_phase = 6 if slug.strip().startswith("dev-loop-") else 4
    phase_num = _normalize_phase(phase, max_phase=max_phase)
    if phase_num is None:
        return None, f"phase inválida: {phase}"

    resolved_event_id = (event_id or "").strip() or str(uuid.uuid4())
    resolved_run_id = (run_id or "").strip() or str(uuid.uuid4())

    payload: dict[str, Any] = {
        "event_type": event_type,
        "ts": ts or datetime.now(timezone.utc).isoformat(),
        "phase": phase_num,
        "agent": agent.strip(),
        "slug": slug.strip(),
        "event_id": resolved_event_id,
        "run_id": resolved_run_id,
    }
    if task_id:
        payload["task_id"] = str(task_id).strip()
    if source:
        payload["source"] = str(source).strip()

    if extra:
        for key, value in extra.items():
            if _is_forbidden_key(key):
                warnings.append(f"stripped forbidden key: {key}")
                continue
            if key not in ALLOWED_KEYS:
                warnings.append(f"stripped unknown key: {key}")
                continue
            if key in payload:
                continue
            payload[key] = value

    # Parent: explícito (param/extra) > stack top (task 76) > omitido (órfão).
    explicit_parent = parent_event_id
    if explicit_parent is None and isinstance(payload.get("parent_event_id"), str):
        explicit_parent = str(payload["parent_event_id"])
    resolved_parent, stack_warn = _resolve_parent(
        explicit=explicit_parent,
        slug=slug.strip(),
        projetos_root=projetos_root,
        event_type=event_type,
        event_id=resolved_event_id,
    )
    if stack_warn:
        warnings.append(stack_warn)
    if resolved_parent:
        payload["parent_event_id"] = resolved_parent
    else:
        payload.pop("parent_event_id", None)

    for key in list(payload):
        if key not in ALLOWED_KEYS:
            del payload[key]
            warnings.append(f"stripped key: {key}")

    if not payload.get("agent"):
        return None, "agent obrigatório"
    if not payload.get("slug"):
        return None, "slug obrigatório"

    return payload, _join_warnings(*warnings) if warnings else None


def _resolve_parent(
    *,
    explicit: str | None,
    slug: str,
    projetos_root: Path | None,
    event_type: str,
    event_id: str,
) -> tuple[str | None, str | None]:
    """Resolve parent_event_id; integra stack fail-soft quando disponível."""
    if explicit is not None and str(explicit).strip():
        parent = str(explicit).strip()
        _stack_touch_after_emit(
            slug=slug,
            projetos_root=projetos_root,
            event_type=event_type,
            event_id=event_id,
        )
        return parent, None
    if projetos_root is None:
        return None, None
    try:
        from config.fluxo_events.stack import (  # noqa: PLC0415
            peek_parent,
            push_event,
            pop_event,
        )

        stack_parent, warn = peek_parent(projetos_root, slug)
        if event_type in {"agent_enter", "task_enter", "phase_enter"}:
            push_warn = push_event(projetos_root, slug, event_id)
            warn = _join_warnings(warn, push_warn)
        elif event_type in {"agent_exit", "task_exit", "phase_exit"}:
            pop_warn = pop_event(projetos_root, slug)
            warn = _join_warnings(warn, pop_warn)
        return stack_parent, warn
    except ImportError:
        return None, None
    except Exception as exc:  # noqa: BLE001 — fail-soft
        return None, f"stack resolve soft: {exc}"


def _stack_touch_after_emit(
    *,
    slug: str,
    projetos_root: Path | None,
    event_type: str,
    event_id: str,
) -> None:
    """Com parent explícito, ainda atualiza a stack (push/pop) fail-soft."""
    if projetos_root is None:
        return
    try:
        from config.fluxo_events.stack import push_event, pop_event  # noqa: PLC0415

        if event_type in {"agent_enter", "task_enter", "phase_enter"}:
            push_event(projetos_root, slug, event_id)
        elif event_type in {"agent_exit", "task_exit", "phase_exit"}:
            pop_event(projetos_root, slug)
    except ImportError:
        return
    except Exception as exc:  # noqa: BLE001
        _warn(f"stack touch soft: {exc}")


def _normalize_phase(phase: int | str, *, max_phase: int = 4) -> int | None:
    if isinstance(phase, int) and not isinstance(phase, bool):
        return phase if 0 <= phase <= max_phase else None
    text = str(phase).strip()
    if text.isdigit():
        num = int(text)
        return num if 0 <= num <= max_phase else None
    upper = text.upper()
    if upper in PHASE_SLUGS:
        num = PHASE_SLUGS[upper]
        return num if 0 <= num <= max_phase else None
    if upper in DEV_LOOP_PHASE_SLUGS:
        num = DEV_LOOP_PHASE_SLUGS[upper]
        return num if 0 <= num <= max_phase else None
    return None


def _is_forbidden_key(key: str) -> bool:
    return any(pattern.search(key) for pattern in FORBIDDEN_KEY_PATTERNS)


def _ensure_fluxo_dir(projetos_root: Path, slug: str) -> Path:
    directory = fluxo_dir_for_slug(projetos_root, slug)
    directory.mkdir(parents=True, exist_ok=True)
    return directory


def _mirror_best_effort(
    repo_root: Path,
    slug: str,
    line: str,
    contract: FluxoEventsContract,
    auto_render: bool,
) -> None:
    try:
        cursor_root = resolve_projetos_root(None, repo_root=repo_root, tree="cursor")
        target = events_path(cursor_root, slug, paths=contract.paths)
        from config.fluxo_events.rotate import append_with_rotate  # noqa: PLC0415

        append_with_rotate(
            target,
            line,
            max_bytes=contract.limits.max_events_bytes,
        )
        if auto_render:
            from config.fluxo_events.render import render_live  # noqa: PLC0415

            render_live(
                slug=slug,
                projetos_root=cursor_root,
                repo_root=repo_root,
            )
    except OSError as exc:
        _warn(f"mirror cursor failed: {exc}")


def _soft_fail(message: str) -> EmitResult:
    _warn(message)
    return EmitResult(
        ok=False,
        soft=True,
        warning=message,
        line=None,
        events_file=None,
        rendered=False,
    )


def _warn(message: str) -> None:
    print(f"[fluxo-events] WARN: {message}", file=sys.stderr)


def _join_warnings(*parts: str | None) -> str | None:
    cleaned = [p for p in parts if p]
    return "; ".join(cleaned) if cleaned else None
