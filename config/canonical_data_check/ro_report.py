"""Job somente-leitura para relatar conformidade do brownfield sql-capacity."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from config.canonical_data_check.constants import (
    DEFAULT_PROFILE,
    EXIT_OK,
    EXIT_USAGE,
)
from config.canonical_data_check.engine import validate_project
from config.canonical_data_check.reporting import ComplianceReport

REPO_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_TARGET = Path("/DATALAKE/workspace/prd/data-sql-capacity-evolution-prd")
DEFAULT_OUTPUT = REPO_ROOT / "reports" / "sql-capacity-compliance.json"


def build_parser() -> argparse.ArgumentParser:
    """Cria o contrato de linha de comando do job RO."""
    parser = argparse.ArgumentParser(
        prog="canonical-data-check-ro-report",
        description=(
            "Gera no canônico um relatório sanitizado sem alterar o projeto-alvo"
        ),
    )
    parser.add_argument(
        "--target",
        type=Path,
        default=DEFAULT_TARGET,
        help=f"Projeto-alvo somente leitura (default: {DEFAULT_TARGET})",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=DEFAULT_OUTPUT,
        help=f"Artefato fora do alvo (default: {DEFAULT_OUTPUT})",
    )
    parser.add_argument(
        "--contract",
        type=Path,
        default=None,
        help="Path para data-engineering.yaml (default: raiz do canônico)",
    )
    parser.add_argument(
        "--profile",
        default=DEFAULT_PROFILE,
        help=f"Perfil normativo (default: {DEFAULT_PROFILE})",
    )
    parser.add_argument(
        "--format",
        choices=("json", "markdown"),
        default="json",
        help="Formato do artefato (default: json)",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    """Executa o scan RO; path ausente é soft-fail intencional."""
    args = build_parser().parse_args(argv)
    target = args.target.resolve()
    output = args.output.resolve()

    if not target.is_dir():
        print(
            f"SOFT-FAIL: projeto-alvo ausente; relatório não gerado: {target}",
            file=sys.stderr,
        )
        return EXIT_OK

    if output.is_relative_to(target):
        print(
            "Artefato inválido: --output deve ficar fora do projeto-alvo somente leitura",
            file=sys.stderr,
        )
        return EXIT_USAGE

    result = validate_project(
        target,
        contract_path=args.contract,
        profile=args.profile,
    )
    report = ComplianceReport.from_validation(result)
    content = _serialize(report, args.format)

    try:
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(content, encoding="utf-8")
    except OSError as exc:
        print(f"Falha ao gravar artefato no canônico: {exc}", file=sys.stderr)
        return EXIT_USAGE

    print(f"Relatório RO gerado: {output}")
    return result.exit_code


def _serialize(report: ComplianceReport, output_format: str) -> str:
    if output_format == "markdown":
        return report.to_markdown()
    return json.dumps(report.to_dict(), ensure_ascii=True, indent=2) + "\n"


if __name__ == "__main__":
    raise SystemExit(main())
