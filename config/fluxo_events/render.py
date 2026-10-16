"""Render de ``live.html`` — mapa SDD 0–4 + highlight ativo + timeline."""

from __future__ import annotations

import html
import json
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from config.fluxo_events.contract import SddPhase
from config.fluxo_events.paths import (
    events_path,
    live_html_path,
    load_contract_or_default,
    resolve_projetos_root,
)

REPO_ROOT = Path(__file__).resolve().parents[2]

PHASE_LABELS: dict[int, str] = {
    0: "IDEIA",
    1: "REQUISITOS",
    2: "PRD_HARNESS",
    3: "IMPLEMENTAR",
    4: "ENCERRAR",
}

DEV_LOOP_PHASE_LABELS: dict[int, str] = {
    0: "LOAD",
    1: "VALIDATE",
    2: "INIT_PICK",
    3: "EXECUTE_VERIFY",
    4: "UPDATE_CHECK",
    5: "LOOP_LOG",
    6: "SYNC",
}

DEV_LOOP_SLUG_PREFIX = "dev-loop-"


@dataclass(frozen=True, slots=True)
class RenderResult:
    """Resultado fail-soft de um render."""

    ok: bool
    soft: bool
    warning: str | None
    html_path: Path | None
    active_phase: int | None
    active_agent: str | None


@dataclass(frozen=True, slots=True)
class ActiveState:
    """Estado ativo derivado do último evento relevante."""

    phase: int | None
    agent: str | None


def render_live(
    *,
    slug: str,
    contract_path: Path | None = None,
    projetos_root: Path | None = None,
    repo_root: Path | None = None,
) -> RenderResult:
    """Gera ``live.html`` com mapa completo mesmo se o log estiver vazio."""
    root = repo_root or REPO_ROOT
    try:
        contract = load_contract_or_default(contract_path, repo_root=root)
        proj_root = resolve_projetos_root(projetos_root, repo_root=root)
        events_file = events_path(proj_root, slug, paths=contract.paths)
        events = _read_events(events_file)
        active = derive_active_state(events)
        phase_map = select_phase_map(slug, contract.sdd_map, contract.dev_loop_map)
        document = build_html(
            slug=slug,
            phase_map=phase_map,
            events=events,
            active=active,
        )
        target = live_html_path(proj_root, slug, paths=contract.paths)
        target.parent.mkdir(parents=True, exist_ok=True)
        _write_html(target, document)
        return RenderResult(
            ok=True,
            soft=False,
            warning=None,
            html_path=target,
            active_phase=active.phase,
            active_agent=active.agent,
        )
    except OSError as exc:
        return _soft_fail(f"render FS error: {exc}")
    except Exception as exc:  # noqa: BLE001 — boundary fail-soft
        return _soft_fail(f"render failed: {exc}")


def derive_active_state(events: list[dict[str, Any]]) -> ActiveState:
    """Destaca agent/fase a partir do último evento relevante."""
    phase: int | None = None
    agent: str | None = None
    for event in reversed(events):
        et = str(event.get("event_type", ""))
        if phase is None and "phase" in event:
            try:
                phase = int(event["phase"])
            except (TypeError, ValueError):
                phase = None
        if agent is None and et in {"agent_enter", "task_enter", "phase_enter"}:
            agent_val = event.get("agent")
            if isinstance(agent_val, str) and agent_val.strip():
                agent = agent_val.strip()
        if phase is not None and agent is not None:
            break
        if phase is None and et.startswith("phase_") and "phase" in event:
            try:
                phase = int(event["phase"])
            except (TypeError, ValueError):
                pass
    if phase is None and events:
        last = events[-1]
        try:
            phase = int(last["phase"])
        except (KeyError, TypeError, ValueError):
            phase = None
        if agent is None:
            agent_val = last.get("agent")
            if isinstance(agent_val, str) and agent_val.strip():
                agent = agent_val.strip()
    return ActiveState(phase=phase, agent=agent)


def select_phase_map(
    slug: str,
    sdd_map: tuple[SddPhase, ...],
    dev_loop_map: tuple[SddPhase, ...],
) -> tuple[SddPhase, ...]:
    """Slug ``dev-loop-*`` → mapa Dev 0–6; demais → SDD 0–4."""
    if slug.startswith(DEV_LOOP_SLUG_PREFIX):
        return dev_loop_map
    return sdd_map


# Geometria do fluxograma SVG (determinística — testável).
_SVG_MARGIN_X = 24
_SVG_COL_W = 210
_SVG_PHASE_W = 168
_SVG_PHASE_H = 48
_SVG_PHASE_Y = 32
_SVG_AGENT_W = 168
_SVG_AGENT_H = 32
_SVG_AGENT_GAP = 12
_SVG_AGENT_Y0 = _SVG_PHASE_Y + _SVG_PHASE_H + 30


def _phase_node_classes(phase_num: int, active: ActiveState) -> str:
    css = "node phase"
    if active.phase is not None:
        if phase_num == active.phase:
            return css + " active"
        if phase_num < active.phase:
            return css + " done"
    return css


def build_flow_svg(
    *,
    phases: tuple[SddPhase, ...],
    active: ActiveState,
    is_dev: bool,
    svg_extra_class: str = "",
) -> str:
    """Gera um fluxograma SVG: nós de fase encadeados por setas + nós de agente.

    Destaca o caminho já executado (fases ``< ativa`` = ``done``; fase ativa =
    ``active``) e o agente ativo. ``svg_extra_class`` (ex.: ``fluxograma-previsto``)
    permite variantes visuais (Opção C — mapa previsto esmaecido).
    """
    labels = DEV_LOOP_PHASE_LABELS if is_dev else PHASE_LABELS
    count = len(phases)
    max_agents = max((len(p.agents) for p in phases), default=0)
    width = _SVG_MARGIN_X * 2 + max(count - 1, 0) * _SVG_COL_W + _SVG_PHASE_W
    height = _SVG_AGENT_Y0 + max_agents * (_SVG_AGENT_H + _SVG_AGENT_GAP) + 16
    phase_cy = _SVG_PHASE_Y + _SVG_PHASE_H / 2
    svg_classes = "fluxograma"
    if svg_extra_class.strip():
        svg_classes += f" {svg_extra_class.strip()}"

    parts: list[str] = [
        f'<svg data-testid="fluxograma" class="{svg_classes}" '
        f'viewBox="0 0 {width} {height}" width="100%" '
        f'preserveAspectRatio="xMinYMin meet" role="img" '
        f'aria-label="Fluxograma do fluxo de agentes">',
        (
            '<defs><marker id="arrowhead" markerWidth="9" markerHeight="9" '
            'refX="7" refY="3" orient="auto" markerUnits="strokeWidth">'
            '<path d="M0,0 L7,3 L0,6 Z" class="arrow-fill"/></marker></defs>'
        ),
    ]

    # Arestas fase→fase (com seta) — desenhadas antes dos nós.
    for idx in range(count - 1):
        x1 = _SVG_MARGIN_X + idx * _SVG_COL_W + _SVG_PHASE_W
        x2 = _SVG_MARGIN_X + (idx + 1) * _SVG_COL_W
        target_phase = phases[idx + 1].phase
        edge_css = "edge"
        if active.phase is not None and target_phase <= active.phase:
            edge_css += " done"
        parts.append(
            f'<line class="{edge_css}" x1="{x1}" y1="{phase_cy:.0f}" '
            f'x2="{x2 - 4}" y2="{phase_cy:.0f}" marker-end="url(#arrowhead)"/>'
        )

    # Nós de fase + nós de agente por coluna.
    for idx, phase in enumerate(phases):
        x = _SVG_MARGIN_X + idx * _SVG_COL_W
        label = phase.slug or labels.get(phase.phase, str(phase.phase))
        node_css = _phase_node_classes(phase.phase, active)
        parts.append(
            f'<g class="{node_css}" data-node-phase="{phase.phase}" '
            f'data-phase="{phase.phase}">'
            f'<rect x="{x}" y="{_SVG_PHASE_Y}" width="{_SVG_PHASE_W}" '
            f'height="{_SVG_PHASE_H}" rx="9"/>'
            f'<text x="{x + _SVG_PHASE_W / 2:.0f}" '
            f'y="{_SVG_PHASE_Y + _SVG_PHASE_H / 2 + 5:.0f}" '
            f'text-anchor="middle">Fase {phase.phase} · '
            f"{html.escape(label)}</text></g>"
        )
        for j, agent_name in enumerate(phase.agents):
            ay = _SVG_AGENT_Y0 + j * (_SVG_AGENT_H + _SVG_AGENT_GAP)
            agent_active = active.phase == phase.phase and active.agent == agent_name
            agent_css = "node-agent active" if agent_active else "node-agent"
            link_css = "link done" if (
                active.phase is not None and phase.phase <= active.phase
            ) else "link"
            connector_y1 = (
                _SVG_AGENT_Y0 - _SVG_AGENT_GAP
                if j == 0
                else ay - _SVG_AGENT_GAP
            )
            parts.append(
                f'<line class="{link_css}" x1="{x + _SVG_AGENT_W / 2:.0f}" '
                f'y1="{connector_y1:.0f}" x2="{x + _SVG_AGENT_W / 2:.0f}" '
                f'y2="{ay:.0f}"/>'
            )
            parts.append(
                f'<g class="{agent_css}" data-node-agent="{html.escape(agent_name)}">'
                f'<rect x="{x}" y="{ay}" width="{_SVG_AGENT_W}" '
                f'height="{_SVG_AGENT_H}" rx="7"/>'
                f'<text x="{x + _SVG_AGENT_W / 2:.0f}" y="{ay + _SVG_AGENT_H / 2 + 5:.0f}" '
                f'text-anchor="middle">{html.escape(agent_name)}</text></g>'
            )

    parts.append("</svg>")
    return "".join(parts)


# Trilha de execução real (Opção C — só agentes usados, setas temporais).
_EXEC_NODE_W = 148
_EXEC_NODE_H = 44
_EXEC_GAP = 44
_EXEC_MARGIN = 28
_EXEC_BADGE_H = 14


def extract_agent_enter_trail(events: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """``agent_enter`` cronológico; colapsa repetições consecutivas do mesmo agente."""
    enters = [
        e
        for e in events
        if str(e.get("event_type", "")) == "agent_enter"
        and isinstance(e.get("agent"), str)
        and str(e.get("agent", "")).strip()
    ]
    enters.sort(key=lambda e: str(e.get("ts", "")))
    trail: list[dict[str, Any]] = []
    last_agent: str | None = None
    for event in enters:
        agent = str(event["agent"]).strip()
        if agent == last_agent:
            continue
        trail.append(event)
        last_agent = agent
    return trail


def agent_enter_completed(
    events: list[dict[str, Any]],
    enter_event: dict[str, Any],
) -> bool:
    """True se existir ``agent_exit`` do mesmo agente após o enter."""
    ts_enter = str(enter_event.get("ts", ""))
    agent = enter_event.get("agent")
    for event in events:
        if (
            str(event.get("event_type", "")) == "agent_exit"
            and event.get("agent") == agent
            and str(event.get("ts", "")) >= ts_enter
        ):
            return True
    return False


def _event_id(event: dict[str, Any]) -> str | None:
    raw = event.get("event_id")
    if isinstance(raw, str) and raw.strip():
        return raw.strip()
    return None


def delegated_children(
    events: list[dict[str, Any]],
    parent_enter: dict[str, Any],
) -> list[dict[str, Any]]:
    """``task_enter`` e ``agent_enter`` filhos (subagentes) ligados por ``parent_event_id``."""
    parent_id = _event_id(parent_enter)
    if not parent_id:
        return []
    parent_agent = str(parent_enter.get("agent", "")).strip()
    children: list[dict[str, Any]] = []
    for event in events:
        et = str(event.get("event_type", ""))
        if event.get("parent_event_id") != parent_id:
            continue
        if et == "task_enter":
            children.append(event)
        elif et == "agent_enter":
            child_agent = str(event.get("agent", "")).strip()
            if child_agent and child_agent != parent_agent:
                children.append(event)
    children.sort(key=lambda item: str(item.get("ts", "")))
    return children


def task_enter_completed(
    events: list[dict[str, Any]],
    task_enter_event: dict[str, Any],
) -> bool:
    """True se existir ``task_exit`` correspondente após o enter."""
    ts_enter = str(task_enter_event.get("ts", ""))
    task_id = task_enter_event.get("task_id")
    agent = task_enter_event.get("agent")
    for event in events:
        if (
            str(event.get("event_type", "")) == "task_exit"
            and event.get("task_id") == task_id
            and event.get("agent") == agent
            and str(event.get("ts", "")) >= ts_enter
        ):
            return True
    return False


def _child_label(event: dict[str, Any]) -> str:
    et = str(event.get("event_type", ""))
    if et == "task_enter":
        task_id = str(event.get("task_id", "?")).strip()
        return f"task {task_id}"
    agent = str(event.get("agent", "")).strip()
    return f"→ {agent}" if agent else "→ subagente"


_EXEC_TASK_H = 26
_EXEC_TASK_GAP = 6
_EXEC_DELEGATE_LINK = 18


def build_execution_trail_svg(
    events: list[dict[str, Any]],
    active: ActiveState,
) -> str:
    """SVG horizontal: agentes + tasks/subagentes delegados sob cada gate."""
    trail = extract_agent_enter_trail(events)
    count = len(trail)
    child_counts = [len(delegated_children(events, enter)) for enter in trail]
    max_children = max(child_counts, default=0)
    extra_h = (
        _EXEC_DELEGATE_LINK + max_children * (_EXEC_TASK_H + _EXEC_TASK_GAP)
        if max_children
        else 0
    )
    width = max(
        _EXEC_MARGIN * 2 + max(count - 1, 0) * (_EXEC_NODE_W + _EXEC_GAP) + _EXEC_NODE_W,
        320,
    )
    height = _EXEC_MARGIN * 2 + _EXEC_NODE_H + _EXEC_BADGE_H + 12 + extra_h

    parts: list[str] = [
        f'<svg data-testid="fluxograma-execucao" class="fluxograma fluxograma-execucao" '
        f'viewBox="0 0 {width:.0f} {height:.0f}" width="100%" '
        f'preserveAspectRatio="xMinYMin meet" role="img" '
        f'aria-label="Trilha de execução real dos agentes">',
        (
            '<defs><marker id="exec-arrow" markerWidth="9" markerHeight="9" '
            'refX="7" refY="3" orient="auto" markerUnits="strokeWidth">'
            '<path d="M0,0 L7,3 L0,6 Z" class="arrow-fill exec-arrow-fill"/>'
            "</marker></defs>"
        ),
    ]

    if not trail:
        parts.append(
            f'<text x="{width / 2:.0f}" y="{height / 2:.0f}" text-anchor="middle" '
            f'class="muted">nenhum agente executado ainda</text>'
        )
        parts.append("</svg>")
        return "".join(parts)

    node_y = _EXEC_MARGIN + _EXEC_BADGE_H
    for idx, event in enumerate(trail):
        x = _EXEC_MARGIN + idx * (_EXEC_NODE_W + _EXEC_GAP)
        agent = str(event.get("agent", "")).strip()
        try:
            phase_num = int(event.get("phase", 0))
        except (TypeError, ValueError):
            phase_num = 0
        completed = agent_enter_completed(events, event)
        is_active = active.agent == agent and not completed
        css = "exec-node done" if completed else "exec-node"
        if is_active:
            css = "exec-node active"
        parts.append(
            f'<g class="{css}" data-exec-agent="{html.escape(agent)}" '
            f'data-exec-phase="{phase_num}">'
            f'<text x="{x + _EXEC_NODE_W / 2:.0f}" y="{_EXEC_MARGIN + 10:.0f}" '
            f'text-anchor="middle" class="exec-badge">F{phase_num}</text>'
            f'<rect x="{x:.0f}" y="{node_y:.0f}" width="{_EXEC_NODE_W}" '
            f'height="{_EXEC_NODE_H}" rx="10"/>'
            f'<text x="{x + _EXEC_NODE_W / 2:.0f}" '
            f'y="{node_y + _EXEC_NODE_H / 2 + 5:.0f}" text-anchor="middle">'
            f"{html.escape(agent)}</text></g>"
        )
        if idx < count - 1:
            x1 = x + _EXEC_NODE_W
            x2 = x + _EXEC_NODE_W + _EXEC_GAP - 6
            mid_y = node_y + _EXEC_NODE_H / 2
            parts.append(
                f'<line class="edge exec-edge" x1="{x1:.0f}" y1="{mid_y:.0f}" '
                f'x2="{x2:.0f}" y2="{mid_y:.0f}" marker-end="url(#exec-arrow)"/>'
            )

        children = delegated_children(events, event)
        if children:
            link_y1 = node_y + _EXEC_NODE_H
            cx = x + _EXEC_NODE_W / 2
            parts.append(
                f'<line class="link exec-delegate-link" x1="{cx:.0f}" y1="{link_y1:.0f}" '
                f'x2="{cx:.0f}" y2="{link_y1 + _EXEC_DELEGATE_LINK:.0f}"/>'
            )
            child_y = link_y1 + _EXEC_DELEGATE_LINK
            for child in children:
                label = _child_label(child)
                child_done = (
                    task_enter_completed(events, child)
                    if str(child.get("event_type")) == "task_enter"
                    else agent_enter_completed(events, child)
                )
                child_css = "exec-child done" if child_done else "exec-child"
                et = str(child.get("event_type", ""))
                if et == "task_enter":
                    tid = html.escape(str(child.get("task_id", "")))
                    parts.append(
                        f'<g class="{child_css} exec-task" data-task-id="{tid}">'
                    )
                else:
                    sub = html.escape(str(child.get("agent", "")))
                    parts.append(
                        f'<g class="{child_css} exec-delegate" '
                        f'data-delegate-agent="{sub}">'
                    )
                parts.append(
                    f'<rect x="{x + 8:.0f}" y="{child_y:.0f}" '
                    f'width="{_EXEC_NODE_W - 16:.0f}" height="{_EXEC_TASK_H:.0f}" rx="6"/>'
                    f'<text x="{cx:.0f}" y="{child_y + _EXEC_TASK_H / 2 + 4:.0f}" '
                    f'text-anchor="middle" class="exec-child-label">'
                    f"{html.escape(label)}</text></g>"
                )
                child_y += _EXEC_TASK_H + _EXEC_TASK_GAP

    parts.append("</svg>")
    return "".join(parts)


def build_resumo_html(
    events: list[dict[str, Any]],
    active: ActiveState,
) -> str:
    """Painel lateral: agentes + tasks/subagentes delegados (Opção C)."""
    trail = extract_agent_enter_trail(events)
    if not trail:
        return '<p class="resumo-empty">Nenhum agente executado ainda.</p>'
    items: list[str] = []
    task_total = 0
    for event in trail:
        agent = str(event.get("agent", "")).strip()
        try:
            phase_num = int(event.get("phase", 0))
        except (TypeError, ValueError):
            phase_num = 0
        completed = agent_enter_completed(events, event)
        is_active = active.agent == agent and not completed
        state = "active" if is_active else ("done" if completed else "pending")
        mark = "✓" if completed else ("▶" if is_active else "·")
        css = f"resumo-item {state}"
        sub_items: list[str] = []
        for child in delegated_children(events, event):
            label = _child_label(child)
            if str(child.get("event_type")) == "task_enter":
                task_total += 1
                child_done = task_enter_completed(events, child)
            else:
                child_done = agent_enter_completed(events, child)
            sub_mark = "✓" if child_done else "·"
            sub_css = "resumo-sub-item done" if child_done else "resumo-sub-item"
            sub_items.append(
                f'<li class="{sub_css}">{sub_mark} {html.escape(label)}</li>'
            )
        sub_html = (
            f'<ul class="resumo-sub">{"".join(sub_items)}</ul>' if sub_items else ""
        )
        items.append(
            f'<li class="{css}" data-phase="{phase_num}" data-agent="{html.escape(agent)}">'
            f'<span class="resumo-mark" aria-hidden="true">{mark}</span>'
            f'<span class="resumo-agent">{html.escape(agent)}</span>'
            f'<span class="resumo-phase">F{phase_num}</span>'
            f"{sub_html}"
            f"</li>"
        )
    agent_plural = "s" if len(trail) != 1 else ""
    task_note = (
        f" · {task_total} task{'s' if task_total != 1 else ''}"
        if task_total
        else ""
    )
    return (
        f'<p class="resumo-count">{len(trail)} agente{agent_plural} utilizado'
        f"{agent_plural}{task_note}</p>"
        f'<ul class="resumo-list">{"".join(items)}</ul>'
    )


def _format_ts_short(ts: str) -> str:
    """HH:MM a partir de ISO timestamp (fail-soft)."""
    text = ts.strip()
    if "T" in text:
        time_part = text.split("T", 1)[1]
        return time_part[:5] if len(time_part) >= 5 else time_part
    return text[:5] if len(text) >= 5 else text


def _duration_minutes(ts_start: str, ts_end: str) -> int | None:
    """Duração arredondada em minutos entre dois ISO (fail-soft)."""
    try:
        from datetime import datetime

        def parse(value: str) -> datetime:
            v = value.replace("Z", "+00:00")
            return datetime.fromisoformat(v)

        delta = parse(ts_end) - parse(ts_start)
        seconds = max(int(delta.total_seconds()), 0)
        return max(seconds // 60, 0)
    except (TypeError, ValueError, OverflowError):
        return None


def build_human_timeline_items(events: list[dict[str, Any]]) -> list[str]:
    """Timeline legível — agentes, tasks e delegações (sem event_type cru)."""
    items: list[str] = []
    top_trail_ids = {_event_id(e) for e in extract_agent_enter_trail(events)}
    activity = [
        e
        for e in events
        if str(e.get("event_type", "")) in {"agent_enter", "task_enter"}
    ]
    activity.sort(key=lambda item: str(item.get("ts", "")))
    for enter in activity[-40:]:
        et = str(enter.get("event_type", ""))
        ts_enter = str(enter.get("ts", ""))
        try:
            phase_num = int(enter.get("phase", 0))
        except (TypeError, ValueError):
            phase_num = 0
        time_label = _format_ts_short(ts_enter)
        prefix = ""
        if et == "agent_enter":
            agent = str(enter.get("agent", "")).strip()
            eid = _event_id(enter)
            if eid and eid not in top_trail_ids:
                prefix = "↳ "
            name = f"<strong>{html.escape(agent)}</strong>"
            exit_ts: str | None = None
            for event in events:
                if (
                    str(event.get("event_type", "")) == "agent_exit"
                    and event.get("agent") == agent
                    and str(event.get("ts", "")) >= ts_enter
                ):
                    exit_ts = str(event.get("ts", ""))
                    break
        else:
            task_id = html.escape(str(enter.get("task_id", "?")).strip())
            agent = str(enter.get("agent", "")).strip()
            prefix = "↳ "
            name = f"<strong>task {task_id}</strong> ({html.escape(agent)})"
            exit_ts = None
            for event in events:
                if (
                    str(event.get("event_type", "")) == "task_exit"
                    and event.get("task_id") == enter.get("task_id")
                    and event.get("agent") == enter.get("agent")
                    and str(event.get("ts", "")) >= ts_enter
                ):
                    exit_ts = str(event.get("ts", ""))
                    break
        if exit_ts:
            mins = _duration_minutes(ts_enter, exit_ts)
            dur = f" · {mins} min" if mins is not None and mins > 0 else ""
            status = f"concluído{dur}"
            css = "summary-event done"
        else:
            status = "em execução"
            css = "summary-event active"
        items.append(
            f'<li class="{css}" data-phase="{phase_num}">'
            f"<time>{html.escape(time_label)}</time> · "
            f"F{phase_num} · {prefix}{name} · "
            f"{html.escape(status)}"
            f"</li>"
        )
    for event in events:
        if str(event.get("event_type", "")) != "ship_truncate":
            continue
        agent = html.escape(str(event.get("agent", "")))
        ts = html.escape(_format_ts_short(str(event.get("ts", ""))))
        try:
            phase_num = int(event.get("phase", 0))
        except (TypeError, ValueError):
            phase_num = 0
        items.append(
            f'<li class="summary-event meta" data-type="ship_truncate">'
            f"<time>{ts}</time> · F{phase_num} · {agent} · fluxo arquivado"
            f"</li>"
        )
        break
    return items


# Geometria do grafo causal (árvore real de execução).
_CAUSAL_NODE_W = 176
_CAUSAL_NODE_H = 40
_CAUSAL_GAP_X = 36
_CAUSAL_GAP_Y = 28
_CAUSAL_MARGIN = 24
_CAUSAL_NODE_TYPES = frozenset({"phase_enter", "agent_enter", "task_enter"})


def truncate_uuid_label(value: str, *, keep: int = 8) -> str:
    """Trunca UUID para label visual (SHOULD — legibilidade)."""
    text = (value or "").strip()
    if len(text) <= keep:
        return text
    return f"{text[:keep]}…"


def build_causal_svg(events: list[dict[str, Any]]) -> str:
    """Gera SVG do grafo causal real (função pura).

    Nós: ``phase_enter`` (raiz quando presente) + ``agent_enter`` + ``task_enter``.
    Exits e ``ship_truncate`` ficam só na timeline — fora deste SVG.
    """
    nodes = [e for e in events if str(e.get("event_type", "")) in _CAUSAL_NODE_TYPES]
    by_id: dict[str, dict[str, Any]] = {}
    for event in nodes:
        eid = event.get("event_id")
        if isinstance(eid, str) and eid.strip():
            by_id[eid.strip()] = event

    children: dict[str | None, list[str]] = {}
    for eid, event in by_id.items():
        raw_parent = event.get("parent_event_id")
        parent: str | None
        if isinstance(raw_parent, str) and raw_parent.strip() in by_id:
            parent = raw_parent.strip()
        else:
            parent = None
        children.setdefault(parent, []).append(eid)

    phase_roots = [
        eid
        for eid, ev in by_id.items()
        if str(ev.get("event_type")) == "phase_enter"
        and (
            not isinstance(ev.get("parent_event_id"), str)
            or str(ev.get("parent_event_id")).strip() not in by_id
        )
    ]
    orphan_roots = children.get(None, [])
    roots = phase_roots or orphan_roots
    if not roots and by_id:
        roots = list(by_id.keys())[:1]

    depth_of: dict[str, int] = {}
    order: list[str] = []
    queue: list[tuple[str, int]] = [(r, 0) for r in roots]
    seen: set[str] = set()
    while queue:
        eid, depth = queue.pop(0)
        if eid in seen:
            continue
        seen.add(eid)
        depth_of[eid] = depth
        order.append(eid)
        for child in children.get(eid, []):
            queue.append((child, depth + 1))
    for eid in by_id:
        if eid not in seen:
            depth_of[eid] = 0
            order.append(eid)
            seen.add(eid)

    at_depth: dict[int, list[str]] = {}
    for eid in order:
        at_depth.setdefault(depth_of[eid], []).append(eid)

    max_depth = max(at_depth.keys(), default=0)
    max_width = max((len(v) for v in at_depth.values()), default=1)
    width: float = (
        _CAUSAL_MARGIN * 2
        + max_width * _CAUSAL_NODE_W
        + max(max_width - 1, 0) * _CAUSAL_GAP_X
    )
    height: float = (
        _CAUSAL_MARGIN * 2
        + (max_depth + 1) * _CAUSAL_NODE_H
        + max_depth * _CAUSAL_GAP_Y
        + 8
    )
    if not by_id:
        width, height = 320.0, 80.0

    positions: dict[str, tuple[float, float]] = {}
    for depth, ids in at_depth.items():
        row_w = len(ids) * _CAUSAL_NODE_W + max(len(ids) - 1, 0) * _CAUSAL_GAP_X
        start_x: float = _CAUSAL_MARGIN + max(
            (width - 2 * _CAUSAL_MARGIN - row_w) / 2.0, 0.0
        )
        y: float = _CAUSAL_MARGIN + depth * (_CAUSAL_NODE_H + _CAUSAL_GAP_Y)
        for i, eid in enumerate(ids):
            x: float = start_x + i * (_CAUSAL_NODE_W + _CAUSAL_GAP_X)
            positions[eid] = (x, y)

    parts: list[str] = [
        f'<svg data-testid="fluxograma-causal" class="fluxograma fluxograma-causal" '
        f'viewBox="0 0 {width:.0f} {height:.0f}" width="100%" '
        f'preserveAspectRatio="xMinYMin meet" role="img" '
        f'aria-label="Grafo causal da execução">',
        (
            '<defs><marker id="causal-arrow" markerWidth="9" markerHeight="9" '
            'refX="7" refY="3" orient="auto" markerUnits="strokeWidth">'
            '<path d="M0,0 L7,3 L0,6 Z" class="arrow-fill"/></marker></defs>'
        ),
    ]

    if not by_id:
        parts.append(
            f'<text x="{width / 2:.0f}" y="{height / 2:.0f}" text-anchor="middle" '
            f'class="muted">sem nós causais ainda</text>'
        )
        parts.append("</svg>")
        return "".join(parts)

    for eid, event in by_id.items():
        raw_parent = event.get("parent_event_id")
        if not isinstance(raw_parent, str) or raw_parent.strip() not in positions:
            continue
        parent = raw_parent.strip()
        if parent not in positions or eid not in positions:
            continue
        x1, y1 = positions[parent]
        x2, y2 = positions[eid]
        parts.append(
            f'<line class="edge causal-edge" '
            f'x1="{x1 + _CAUSAL_NODE_W / 2:.0f}" y1="{y1 + _CAUSAL_NODE_H:.0f}" '
            f'x2="{x2 + _CAUSAL_NODE_W / 2:.0f}" y2="{y2:.0f}" '
            f'marker-end="url(#causal-arrow)"/>'
        )

    root_set = set(phase_roots) if phase_roots else set(roots)
    for eid in order:
        event = by_id[eid]
        x, y = positions[eid]
        et = html.escape(str(event.get("event_type", "")))
        agent = html.escape(str(event.get("agent", "")))
        label_id = truncate_uuid_label(eid)
        role = ' data-causal-role="root"' if eid in root_set else ""
        css = "node causal-node"
        if eid in root_set:
            css += " causal-root"
        if et == "task_enter":
            css += " causal-task"
        parts.append(
            f'<g class="{css}" data-event-type="{et}" '
            f'data-event-id="{html.escape(eid)}"{role}>'
            f'<rect x="{x:.0f}" y="{y:.0f}" width="{_CAUSAL_NODE_W}" '
            f'height="{_CAUSAL_NODE_H}" rx="8"/>'
            f'<text x="{x + _CAUSAL_NODE_W / 2:.0f}" y="{y + 16:.0f}" '
            f'text-anchor="middle">{et}</text>'
            f'<text x="{x + _CAUSAL_NODE_W / 2:.0f}" y="{y + 32:.0f}" '
            f'text-anchor="middle" class="causal-id">'
            f"{html.escape(label_id)} · {agent}</text>"
            f"</g>"
        )

    parts.append("</svg>")
    return "".join(parts)


def build_html(
    *,
    slug: str,
    phase_map: tuple[SddPhase, ...],
    events: list[dict[str, Any]],
    active: ActiveState,
    sdd_map: tuple[SddPhase, ...] | None = None,
) -> str:
    """Monta HTML Opção C: previsto esmaecido + trilha real + resumo + timeline humana."""
    phases = phase_map if phase_map is not None else (sdd_map or ())
    is_dev = slug.startswith(DEV_LOOP_SLUG_PREFIX)
    map_title = "Mapa Dev Loop 0–6" if is_dev else "Mapa SDD 0–4"
    previsto_svg = build_flow_svg(
        phases=phases,
        active=active,
        is_dev=is_dev,
        svg_extra_class="fluxograma-previsto",
    )
    exec_svg = build_execution_trail_svg(events, active)
    resumo_html = build_resumo_html(events, active)

    timeline_items = build_human_timeline_items(events)
    if not timeline_items:
        timeline_items = ['<li class="summary-event empty">sem execução registrada</li>']

    active_label = (
        f"fase {active.phase} / {html.escape(active.agent or '—')}"
        if active.phase is not None
        else "nenhum ativo"
    )

    return f"""<!DOCTYPE html>
<html lang="pt-BR">
<head>
  <meta charset="utf-8"/>
  <meta name="viewport" content="width=device-width, initial-scale=1"/>
  <title>Fluxo live — {html.escape(slug)}</title>
  <style>
    :root {{
      --bg: #0f1419;
      --panel: #1a2332;
      --text: #e7ecf3;
      --muted: #8b9bb4;
      --accent: #3d8bfd;
      --active: #f0a500;
    }}
    body {{
      margin: 0; font-family: "IBM Plex Sans", "Segoe UI", sans-serif;
      background: radial-gradient(1200px 600px at 10% -10%, #1e3a5f 0%, var(--bg) 55%);
      color: var(--text); min-height: 100vh;
    }}
    header {{
      padding: 1.5rem 2rem 0.5rem; border-bottom: 1px solid #243044;
    }}
    header h1 {{ margin: 0; font-size: 1.4rem; letter-spacing: 0.02em; }}
    header .meta {{ color: var(--muted); margin-top: 0.35rem; font-size: 0.9rem; }}
    main.layout-c {{
      display: grid; grid-template-columns: 1fr 300px; gap: 1.25rem;
      padding: 1.25rem 2rem 2rem;
    }}
    @media (max-width: 960px) {{ main.layout-c {{ grid-template-columns: 1fr; }} }}
    .graph, .resumo, .timeline {{
      background: color-mix(in srgb, var(--panel) 92%, black);
      border: 1px solid #2a3a52; border-radius: 10px; padding: 0.75rem 1rem 1rem;
    }}
    .graph-previsto {{ grid-column: 1 / -1; opacity: 0.92; }}
    .exec-row {{
      grid-column: 1 / -1;
      display: grid; grid-template-columns: 1fr 300px; gap: 1.25rem;
    }}
    @media (max-width: 960px) {{ .exec-row {{ grid-template-columns: 1fr; }} }}
    .graph h2, .resumo h2, .timeline h2 {{ margin: 0 0 0.5rem; font-size: 1rem; }}
    .graph-sub {{ color: var(--muted); font-size: 0.82rem; margin: 0 0 0.65rem; }}
    .fluxograma {{ display: block; min-width: 640px; }}
    .fluxograma text {{
      fill: var(--text); font-size: 13px;
      font-family: "IBM Plex Sans", "Segoe UI", sans-serif;
    }}
    .fluxograma-previsto {{ opacity: 0.48; filter: saturate(0.65); }}
    .fluxograma-previsto .node rect {{ fill: #141c2a; stroke: #2a3548; }}
    .fluxograma-previsto .node-agent rect {{ fill: #161e2e; stroke: #2a3548; }}
    .fluxograma-previsto .node.done rect {{ stroke: #3a5080; }}
    .fluxograma-previsto .edge {{ stroke: #2a3548; }}
    .fluxograma .node rect {{ fill: #1c2942; stroke: #334860; stroke-width: 1.5; }}
    .fluxograma .node.done rect {{ stroke: var(--accent); }}
    .fluxograma .node.done text {{ fill: #cfe0ff; }}
    .fluxograma .node.active rect {{ fill: #2a2418; stroke: var(--active); stroke-width: 2.5; }}
    .fluxograma .node.active text {{ fill: var(--active); font-weight: 600; }}
    .fluxograma .node-agent rect {{ fill: #20293a; stroke: #334860; stroke-width: 1.2; }}
    .fluxograma .node-agent text {{ font-size: 12px; }}
    .fluxograma .node-agent.active rect {{ fill: var(--active); stroke: #ffd36a; }}
    .fluxograma .node-agent.active text {{ fill: #1a1200; font-weight: 600; }}
    .fluxograma .edge {{ stroke: #3a4a63; stroke-width: 2; }}
    .fluxograma .edge.done {{ stroke: var(--accent); }}
    .fluxograma .link {{ stroke: #2c3a52; stroke-width: 1.2; stroke-dasharray: 3 3; }}
    .fluxograma .link.done {{ stroke: #34558a; }}
    .fluxograma .arrow-fill {{ fill: #3a4a63; }}
    .fluxograma-execucao .exec-node rect {{
      fill: #1c2942; stroke: #4a6a9a; stroke-width: 2;
    }}
    .fluxograma-execucao .exec-node.done rect {{ stroke: var(--accent); }}
    .fluxograma-execucao .exec-node.active rect {{
      fill: #2a2418; stroke: var(--active); stroke-width: 2.5;
    }}
    .fluxograma-execucao .exec-node.active text {{ fill: var(--active); font-weight: 700; }}
    .fluxograma-execucao .exec-badge {{
      fill: var(--muted); font-size: 10px; font-weight: 600;
    }}
    .fluxograma-execucao .exec-edge {{ stroke: var(--accent); stroke-width: 2.5; }}
    .fluxograma-execucao .exec-arrow-fill {{ fill: var(--accent); }}
    .fluxograma-execucao .exec-delegate-link {{
      stroke: #3a4a63; stroke-width: 1.2; stroke-dasharray: 3 3;
    }}
    .fluxograma-execucao .exec-child rect {{
      fill: #182030; stroke: #44556e; stroke-width: 1.2;
    }}
    .fluxograma-execucao .exec-child.done rect {{ stroke: var(--accent); }}
    .fluxograma-execucao .exec-child-label {{
      font-size: 11px; fill: #b8c8e0;
    }}
    .resumo-sub-item.done {{ color: #8fa8c8; }}
    .resumo-count {{ margin: 0 0 0.65rem; color: var(--muted); font-size: 0.85rem; }}
    .resumo-list {{ list-style: none; margin: 0; padding: 0; }}
    .resumo-item {{
      display: grid; grid-template-columns: 1.2rem 1fr auto; gap: 0.35rem;
      align-items: start; padding: 0.35rem 0; border-bottom: 1px solid #243044;
      font-size: 0.85rem;
    }}
    .resumo-sub {{
      list-style: none; margin: 0.35rem 0 0 1.5rem; padding: 0;
      grid-column: 1 / -1; font-size: 0.8rem; color: var(--muted);
    }}
    .resumo-sub-item {{ margin-bottom: 0.2rem; }}
    .resumo-sub-item.done {{ color: #8fa8c8; }}
    .resumo-item:last-child {{ border-bottom: none; }}
    .resumo-item.done .resumo-mark {{ color: #3ecf8e; }}
    .resumo-item.active .resumo-agent {{ color: var(--active); font-weight: 600; }}
    .resumo-phase {{
      color: var(--muted); font-size: 0.75rem; padding: 0.1rem 0.35rem;
      border: 1px solid #334860; border-radius: 4px;
    }}
    .resumo-empty {{ color: var(--muted); font-size: 0.85rem; margin: 0; }}
    .timeline {{ grid-column: 1 / -1; }}
    .timeline ol {{ margin: 0; padding-left: 1.1rem; color: var(--muted); }}
    .summary-event {{ margin-bottom: 0.45rem; font-size: 0.85rem; }}
    .summary-event.done {{ color: #a8b8d0; }}
    .summary-event.active {{ color: var(--active); }}
    .summary-event.meta {{ font-size: 0.8rem; opacity: 0.85; }}
    .timeline time {{ color: var(--accent); }}
    .muted {{ fill: var(--muted); }}
  </style>
</head>
<body>
  <header>
    <h1>Visão gráfica do fluxo</h1>
    <p class="meta">slug: <strong>{html.escape(slug)}</strong> · ativo: {active_label}</p>
  </header>
  <main class="layout-c">
    <section class="graph graph-previsto" data-testid="graph">
      <h2>Mapa previsto — {map_title}</h2>
      <p class="graph-sub">Referência canônica (todos os agentes possíveis por fase)</p>
      {previsto_svg}
    </section>
    <div class="exec-row">
      <section class="graph graph-exec" data-testid="graph-execucao">
        <h2>Execução real</h2>
        <p class="graph-sub">Agentes utilizados neste fluxo, em ordem, com setas de ligação</p>
        {exec_svg}
      </section>
      <aside class="resumo" data-testid="resumo-execucao">
        <h2>Resumo</h2>
        {resumo_html}
      </aside>
    </div>
    <aside class="timeline" data-testid="timeline">
      <h2>Atividade</h2>
      <ol>{"".join(timeline_items)}</ol>
    </aside>
  </main>
</body>
</html>
"""


def _read_events(path: Path) -> list[dict[str, Any]]:
    if not path.is_file():
        return []
    events: list[dict[str, Any]] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        text = line.strip()
        if not text:
            continue
        try:
            payload = json.loads(text)
        except json.JSONDecodeError:
            continue
        if isinstance(payload, dict):
            events.append(payload)
    return events


def _write_html(path: Path, document: str) -> None:
    """Seam de escrita HTML (testável para fail-soft)."""
    path.write_text(document, encoding="utf-8")


def _soft_fail(message: str) -> RenderResult:
    print(f"[fluxo-events] WARN: {message}", file=sys.stderr)
    return RenderResult(
        ok=False,
        soft=True,
        warning=message,
        html_path=None,
        active_phase=None,
        active_agent=None,
    )
