"""CLI argparse — entrypoint ``canonical-data-check``."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from config.canonical_data_check.baseline import compare_project, write_baseline
from config.canonical_data_check.constants import EXIT_OK, EXIT_USAGE
from config.canonical_data_check.engine import default_contract_path, validate_project
from config.canonical_data_check.findings import Finding, ValidationResult
from config.canonical_data_check.reporting import (
    ComplianceReport,
    explain_rule,
)
from config.data_engineering import UnknownRuleError


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="canonical-data-check",
        description="Kernel de conformidade de Engenharia de Dados (Loop 1)",
    )
    sub = parser.add_subparsers(dest="command")

    for name, help_text in (
        ("validate", "Valida um path de projeto (A+B+C)"),
        ("baseline", "Grava snapshot de findings em .harness/data-check/"),
        ("compare", "Compara findings vs baseline + waivers (ratchet)"),
    ):
        cmd = sub.add_parser(name, help=help_text)
        _add_project_arguments(cmd)
        cmd.add_argument(
            "--format",
            choices=("text", "json"),
            default="text",
            help="Formato de saída",
        )

    report = sub.add_parser(
        "report",
        help="Emite findings sanitizados para humanos ou máquinas",
    )
    _add_project_arguments(report)
    report.add_argument(
        "--format",
        choices=("json", "markdown"),
        default="markdown",
        help="Formato do relatório (default: markdown)",
    )

    explain = sub.add_parser(
        "explain",
        help="Explica uma regra da fonte normativa",
    )
    explain.add_argument("rule_id", help="ID normativo, por exemplo DE-B002")
    explain.add_argument(
        "--contract",
        default=None,
        help="Path para data-engineering.yaml (default: raiz do canônico)",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    """API pública testável da CLI. Retorna exit code estável."""
    parser = build_parser()
    try:
        args = parser.parse_args(argv)
    except SystemExit as exc:
        code = exc.code
        if code in (None, 0):
            return 0
        return int(code) if isinstance(code, int) else EXIT_USAGE

    if args.command == "explain":
        return _run_explain(args)

    if args.command not in {"validate", "baseline", "compare", "report"}:
        parser.print_help(sys.stderr)
        return EXIT_USAGE

    if not getattr(args, "path", None):
        parser.print_help(sys.stderr)
        return EXIT_USAGE

    result = _dispatch(args)
    if args.command == "report":
        _emit_report(ComplianceReport.from_validation(result), args.format)
    else:
        _emit(result, args.format)
    return result.exit_code


def _add_project_arguments(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("path", help="Diretório do projeto-alvo")
    parser.add_argument(
        "--contract",
        default=None,
        help="Path para data-engineering.yaml (default: raiz do canônico)",
    )
    parser.add_argument(
        "--profile",
        default="spark-yarn-airflow",
        help="Perfil normativo (default: spark-yarn-airflow)",
    )


def _dispatch(args: argparse.Namespace) -> ValidationResult:
    contract = Path(args.contract) if args.contract else None
    if args.command == "validate":
        return validate_project(
            args.path, contract_path=contract, profile=args.profile
        )
    if args.command == "baseline":
        return write_baseline(
            args.path, contract_path=contract, profile=args.profile
        )
    if args.command == "compare":
        return compare_project(
            args.path, contract_path=contract, profile=args.profile
        )
    return validate_project(
        args.path, contract_path=contract, profile=args.profile
    )


def _run_explain(args: argparse.Namespace) -> int:
    contract = Path(args.contract) if args.contract else default_contract_path()
    try:
        explanation = explain_rule(args.rule_id, contract)
    except UnknownRuleError:
        print(f"Regra inexistente: {args.rule_id}", file=sys.stderr)
        return EXIT_USAGE
    except (OSError, ValueError) as exc:
        print(f"Falha ao carregar contrato: {exc}", file=sys.stderr)
        return EXIT_USAGE
    print(explanation.to_text(), end="")
    return EXIT_OK


def _emit(result: ValidationResult, fmt: str) -> None:
    if fmt == "json":
        print(json.dumps(result.to_dict(), ensure_ascii=True, indent=2))
        return
    _print_text(result.findings)
    print(f"exit_code={result.exit_code} profile={result.profile}")


def _emit_report(report: ComplianceReport, fmt: str) -> None:
    if fmt == "json":
        print(json.dumps(report.to_dict(), ensure_ascii=True, indent=2))
        return
    print(report.to_markdown(), end="")


def _print_text(findings: tuple[Finding, ...]) -> None:
    if not findings:
        print("PASS — nenhum finding")
        return
    for item in findings:
        status = item.status.upper()
        print(f"{status:8} {item.rule_id} {item.path} — {item.message}")


if __name__ == "__main__":
    raise SystemExit(main())
