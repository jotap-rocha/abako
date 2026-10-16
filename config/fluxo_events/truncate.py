"""Truncate do log de eventos (ship G4-b) + re-render."""

from __future__ import annotations

import sys
from dataclasses import dataclass
from pathlib import Path

from config.fluxo_events.emit import emit_event
from config.fluxo_events.paths import (
    events_path,
    load_contract_or_default,
    resolve_projetos_root,
)
from config.fluxo_events.render import render_live

REPO_ROOT = Path(__file__).resolve().parents[2]


@dataclass(frozen=True, slots=True)
class TruncateResult:
    """Resultado fail-soft de truncate."""

    ok: bool
    soft: bool
    warning: str | None
    kept: int
    events_file: Path | None
    rendered: bool


def truncate_events(
    *,
    slug: str,
    keep: int | None = None,
    contract_path: Path | None = None,
    projetos_root: Path | None = None,
    repo_root: Path | None = None,
    emit_ship_event: bool = True,
    auto_render: bool = True,
    agent: str = "harness-ship",
    phase: int = 4,
) -> TruncateResult:
    """Mantém as últimas ``keep`` linhas e re-renderiza ``live.html``."""
    root = repo_root or REPO_ROOT
    try:
        contract = load_contract_or_default(contract_path, repo_root=root)
        n = keep if keep is not None else contract.limits.truncate_keep_default
        if n < 1:
            return _soft_fail("keep deve ser >= 1", kept=0)

        proj_root = resolve_projetos_root(projetos_root, repo_root=root)
        target = events_path(proj_root, slug, paths=contract.paths)
        kept = _truncate_file(target, n)

        if emit_ship_event:
            emit_event(
                slug=slug,
                event_type="ship_truncate",
                agent=agent,
                phase=phase,
                contract_path=contract_path,
                projetos_root=proj_root,
                repo_root=root,
                auto_render=False,
                source="cli",
            )
            # reconta após o evento de truncate
            if target.is_file():
                lines = [
                    ln
                    for ln in target.read_text(encoding="utf-8").splitlines()
                    if ln.strip()
                ]
                if len(lines) > n:
                    _truncate_file(target, n)
                kept = min(len(lines), n)

        rendered = False
        if auto_render:
            render_result = render_live(
                slug=slug,
                contract_path=contract_path,
                projetos_root=proj_root,
                repo_root=root,
            )
            rendered = render_result.ok
            if not render_result.ok:
                return TruncateResult(
                    ok=False,
                    soft=True,
                    warning=render_result.warning,
                    kept=kept,
                    events_file=target,
                    rendered=False,
                )

        return TruncateResult(
            ok=True,
            soft=False,
            warning=None,
            kept=kept,
            events_file=target,
            rendered=rendered,
        )
    except OSError as exc:
        return _soft_fail(f"truncate FS error: {exc}", kept=0)
    except Exception as exc:  # noqa: BLE001 — boundary fail-soft
        return _soft_fail(f"truncate failed: {exc}", kept=0)


def _truncate_file(path: Path, keep: int) -> int:
    """Seam de truncate (testável). Mantém as últimas ``keep`` linhas não vazias."""
    if not path.is_file():
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("", encoding="utf-8")
        return 0
    lines = [ln for ln in path.read_text(encoding="utf-8").splitlines() if ln.strip()]
    kept_lines = lines[-keep:] if keep < len(lines) else lines
    path.write_text(
        ("\n".join(kept_lines) + ("\n" if kept_lines else "")),
        encoding="utf-8",
    )
    return len(kept_lines)


def _soft_fail(message: str, *, kept: int) -> TruncateResult:
    print(f"[fluxo-events] WARN: {message}", file=sys.stderr)
    return TruncateResult(
        ok=False,
        soft=True,
        warning=message,
        kept=kept,
        events_file=None,
        rendered=False,
    )
