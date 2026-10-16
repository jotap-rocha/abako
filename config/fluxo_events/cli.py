"""CLI ``python -m config.fluxo_events emit|render|truncate``."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from config.fluxo_events.contract import FluxoEventsContract

DEFAULT_CONTRACT = Path(__file__).resolve().parents[2] / "fluxo-events.yaml"
REPO_ROOT = Path(__file__).resolve().parents[2]


def main(argv: list[str] | None = None) -> int:
    """Entry point da CLI fluxo-events (fail-soft: erros de operação → exit 0)."""
    parser = argparse.ArgumentParser(
        prog="python -m config.fluxo_events",
        description=(
            "Kernel fluxo-events: emit/render/truncate telemetria live SDD "
            "(fail-soft; nunca bloqueia o fluxo)"
        ),
    )
    sub = parser.add_subparsers(dest="command", required=True)

    emit_p = sub.add_parser("emit", help="Appenda 1 linha JSONL de metadados")
    emit_p.add_argument("--slug", required=True)
    emit_p.add_argument("--event-type", required=True)
    emit_p.add_argument("--agent", required=True)
    emit_p.add_argument("--phase", required=True)
    emit_p.add_argument("--task-id", default=None)
    emit_p.add_argument("--source", default=None)
    emit_p.add_argument(
        "--run-id",
        default=None,
        help="UUID de sessão/slug (auto se omitido)",
    )
    emit_p.add_argument(
        "--parent-event-id",
        default=None,
        help="UUID do evento pai (explícito vence stack)",
    )
    emit_p.add_argument(
        "--no-render",
        action="store_true",
        help="Opt-out do auto-render após emit",
    )
    emit_p.add_argument("--projetos-root", type=Path, default=None)
    emit_p.add_argument("--contract", type=Path, default=DEFAULT_CONTRACT)
    emit_p.add_argument(
        "--mirror-cursor",
        action="store_true",
        help="Espelha append/render em .cursor/projetos/",
    )
    emit_p.add_argument(
        "--print-event-id",
        action="store_true",
        help="Stdout: só o event_id UUID (para BUILD_ENTER_EVENT_ID=$(…))",
    )
    emit_p.add_argument(
        "--json",
        action="store_true",
        help="Stdout: linha JSONL completa do evento (mutuamente exclusivo com --print-event-id)",
    )

    render_p = sub.add_parser("render", help="Regenera live.html a partir do JSONL")
    render_p.add_argument("--slug", required=True)
    render_p.add_argument("--projetos-root", type=Path, default=None)
    render_p.add_argument("--contract", type=Path, default=DEFAULT_CONTRACT)

    trunc_p = sub.add_parser(
        "truncate",
        help="Mantém últimas N linhas (default contrato) e re-render",
    )
    trunc_p.add_argument("--slug", required=True)
    trunc_p.add_argument(
        "--keep",
        type=int,
        default=None,
        help="Linhas a manter (default: limits.truncate_keep_default)",
    )
    trunc_p.add_argument("--projetos-root", type=Path, default=None)
    trunc_p.add_argument("--contract", type=Path, default=DEFAULT_CONTRACT)
    trunc_p.add_argument(
        "--no-ship-event",
        action="store_true",
        help="Não emite event_type=ship_truncate",
    )
    trunc_p.add_argument("--no-render", action="store_true")

    check_p = sub.add_parser("check", help="Valida fluxo-events.yaml")
    check_p.add_argument("--path", type=Path, default=DEFAULT_CONTRACT)

    args = parser.parse_args(argv)

    if args.command == "check":
        return _cmd_check(args.path)
    if args.command == "emit":
        return _cmd_emit(args)
    if args.command == "render":
        return _cmd_render(args)
    if args.command == "truncate":
        return _cmd_truncate(args)
    return 2


def _cmd_check(path: Path) -> int:
    try:
        contract = FluxoEventsContract.load(path)
    except Exception as exc:  # noqa: BLE001 — boundary CLI
        print(f"check failed: {exc}", file=sys.stderr)
        return 1
    print(
        f"ok: version={contract.version} "
        f"max_events_bytes={contract.limits.max_events_bytes} "
        f"truncate_keep_default={contract.limits.truncate_keep_default} "
        f"sdd_phases={len(contract.sdd_map)} "
        f"dev_loop_phases={len(contract.dev_loop_map)}"
    )
    return 0


def _cmd_emit(args: argparse.Namespace) -> int:
    from config.fluxo_events.emit import emit_event

    if args.print_event_id and args.json:
        print(
            "emit failed: --print-event-id and --json are mutually exclusive",
            file=sys.stderr,
        )
        return 2

    result = emit_event(
        slug=args.slug,
        event_type=args.event_type,
        agent=args.agent,
        phase=args.phase,
        task_id=args.task_id,
        source=args.source,
        run_id=args.run_id,
        parent_event_id=args.parent_event_id,
        contract_path=args.contract,
        projetos_root=args.projetos_root,
        repo_root=REPO_ROOT,
        auto_render=not args.no_render,
        mirror_cursor=args.mirror_cursor,
    )
    if result.ok:
        if args.print_event_id:
            if result.event_id:
                print(result.event_id)
            if result.warning:
                print(f"warning: {result.warning}", file=sys.stderr)
            return 0
        if args.json:
            if result.line:
                print(result.line)
            if result.warning:
                print(f"warning: {result.warning}", file=sys.stderr)
            return 0
        print(f"ok: appended {result.events_file}")
        if result.warning:
            print(f"warning: {result.warning}", file=sys.stderr)
        return 0
    # fail-soft: não bloqueia SDD
    print(f"soft-fail: {result.warning}", file=sys.stderr)
    return 0


def _cmd_render(args: argparse.Namespace) -> int:
    from config.fluxo_events.render import render_live

    result = render_live(
        slug=args.slug,
        contract_path=args.contract,
        projetos_root=args.projetos_root,
        repo_root=REPO_ROOT,
    )
    if result.ok:
        print(f"ok: wrote {result.html_path}")
        return 0
    print(f"soft-fail: {result.warning}", file=sys.stderr)
    return 0


def _cmd_truncate(args: argparse.Namespace) -> int:
    from config.fluxo_events.truncate import truncate_events

    result = truncate_events(
        slug=args.slug,
        keep=args.keep,
        contract_path=args.contract,
        projetos_root=args.projetos_root,
        repo_root=REPO_ROOT,
        emit_ship_event=not args.no_ship_event,
        auto_render=not args.no_render,
    )
    if result.ok:
        print(f"ok: kept={result.kept} file={result.events_file}")
        return 0
    print(f"soft-fail: {result.warning}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
