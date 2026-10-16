"""CLI ``python -m config.evidence_gate collect|check``."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from config.evidence_gate.contract import EvidenceGateContract

DEFAULT_CONTRACT = Path(__file__).resolve().parents[2] / "evidence-gate.yaml"


def main(argv: list[str] | None = None) -> int:
    """Entry point da CLI evidence-gate."""
    parser = argparse.ArgumentParser(
        prog="python -m config.evidence_gate",
        description="Kernel evidence-gate: collect provas e check manifesto por task",
    )
    sub = parser.add_subparsers(dest="action", required=True)

    check_p = sub.add_parser(
        "check",
        help="Valida contrato (--contract) ou manifesto de evidências",
    )
    check_p.add_argument(
        "--contract",
        action="store_true",
        help="Valida apenas evidence-gate.yaml (schema tipado)",
    )
    check_p.add_argument(
        "--path",
        type=Path,
        default=DEFAULT_CONTRACT,
        help="Path do contrato YAML (default: raiz do repo)",
    )
    check_p.add_argument(
        "--root",
        type=Path,
        default=None,
        help="Raiz evidencias/ (tasks|logs|audit.jsonl)",
    )
    check_p.add_argument(
        "--task",
        type=str,
        default=None,
        help="task_id do manifesto a validar",
    )
    check_p.add_argument(
        "--entregas",
        type=Path,
        default=None,
        help="Path de metrics/entregas.jsonl para validar evidencias_ref",
    )
    check_p.add_argument(
        "--issue",
        type=int,
        default=None,
        help="Número da issue/task na linha de entregas",
    )

    collect_p = sub.add_parser(
        "collect",
        help="Executa comando do critério e grava log + manifesto (LWW)",
    )
    collect_p.add_argument(
        "--path",
        type=Path,
        default=DEFAULT_CONTRACT,
        help="Path do contrato YAML",
    )
    collect_p.add_argument(
        "--root",
        type=Path,
        required=True,
        help="Raiz evidencias/",
    )
    collect_p.add_argument("--task", type=str, required=True)
    collect_p.add_argument("--criterion", type=str, required=True)
    collect_p.add_argument(
        "--command",
        type=str,
        default=None,
        help="Comando a executar (override ou seed do manifesto)",
    )
    collect_p.add_argument(
        "--test-path",
        action="append",
        default=[],
        dest="test_paths",
        help="Path(s) de teste associados (pode repetir)",
    )
    collect_p.add_argument(
        "--cwd",
        type=Path,
        default=None,
        help="Working directory do subprocess (default: cwd atual)",
    )

    args = parser.parse_args(argv)

    if args.action == "check":
        if args.contract:
            return _cmd_check_contract(args.path)
        if args.root is None:
            print(
                "check exige --contract (valida YAML) ou --root + --task "
                "(valida manifesto)",
                file=sys.stderr,
            )
            return 2
        return _cmd_check_manifest(args)
    if args.action == "collect":
        return _cmd_collect(args)
    return 2


def _cmd_check_contract(path: Path) -> int:
    try:
        contract = EvidenceGateContract.load(path)
    except Exception as exc:  # noqa: BLE001 — boundary CLI
        print(f"check --contract failed: {exc}", file=sys.stderr)
        return 1
    print(
        f"ok: version={contract.version} "
        f"max_log_bytes={contract.limits.max_log_bytes} "
        f"collect_time_factor={contract.limits.collect_time_factor}"
    )
    return 0


def _cmd_check_manifest(args: argparse.Namespace) -> int:
    from config.evidence_gate.check import check_task  # noqa: PLC0415

    if args.root is None or args.task is None:
        print(
            "check manifesto exige --root e --task "
            "(ou use --contract para validar só o YAML)",
            file=sys.stderr,
        )
        return 2
    try:
        result = check_task(
            root=args.root,
            task_id=args.task,
            contract_path=args.path,
            entregas_path=args.entregas,
            issue=args.issue,
            ref_base=args.entregas.parent if args.entregas else None,
        )
    except Exception as exc:  # noqa: BLE001 — boundary CLI
        print(f"check failed: {exc}", file=sys.stderr)
        return 1
    if not result.ok:
        for err in result.errors:
            print(f"check failed: {err}", file=sys.stderr)
        return 1
    print(f"ok: task={args.task} criteria={result.criteria_checked}")
    return 0


def _cmd_collect(args: argparse.Namespace) -> int:
    from config.evidence_gate.collect import collect_criterion  # noqa: PLC0415

    try:
        outcome = collect_criterion(
            root=args.root,
            task_id=args.task,
            criterion_id=args.criterion,
            command=args.command,
            test_paths=tuple(args.test_paths),
            contract_path=args.path,
            cwd=args.cwd,
        )
    except Exception as exc:  # noqa: BLE001 — boundary CLI
        print(f"collect failed: {exc}", file=sys.stderr)
        return 1
    print(
        f"collected: task={outcome.task_id} criterion={outcome.criterion_id} "
        f"exit_code={outcome.exit_code} log={outcome.log_path}"
    )
    return 0 if outcome.collect_ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
