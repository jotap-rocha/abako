"""Checks do pacote B — perfil spark-yarn-airflow."""

from __future__ import annotations

import re
from pathlib import Path

from config.canonical_data_check.findings import Finding
from config.canonical_data_check.scanner import TextFile

_LAYER_TOKENS = (
    "bronze",
    "silver",
    "gold",
    "landing",
    "processed",
    "medallion",
)
_SELECT_STAR = re.compile(r"(?i)\bSELECT\s+\*(?:\s*,|\s+FROM\b|\s*$)")
_VERSION_FIELD = re.compile(r"(?i)^\s*version\s*:", re.MULTILINE)
_TRANSFORM_SUFFIXES = frozenset({".sql", ".py"})


def check_package_b(project_root: Path, files: tuple[TextFile, ...]) -> tuple[Finding, ...]:
    """Executa checks de perfil B001–B003."""
    findings: list[Finding] = []
    findings.extend(_check_layers(project_root, files))
    findings.extend(_check_select_star(files))
    findings.extend(_check_data_contract(project_root, files))
    return tuple(findings)


def _fail(rule_id: str, path: str, message: str) -> Finding:
    return Finding(
        rule_id=rule_id,
        severity="blocker",
        status="fail",
        path=path,
        message=message,
    )


def _check_layers(project_root: Path, files: tuple[TextFile, ...]) -> list[Finding]:
    for name in _LAYER_TOKENS:
        if (project_root / name).is_dir():
            return []
        if (project_root / "pipelines" / name).is_dir():
            return []
        if (project_root / "data" / name).is_dir():
            return []

    for file in files:
        lowered = file.text.lower()
        if "layers:" in lowered and any(token in lowered for token in _LAYER_TOKENS):
            return []
        if sum(1 for token in ("bronze", "silver", "gold") if token in lowered) >= 2:
            return []
        if "landing" in lowered and "processed" in lowered:
            return []

    return [
        _fail(
            "DE-B001",
            ".",
            "Camadas de dados não declaradas (medalhão ou landing/processed)",
        )
    ]


def _check_select_star(files: tuple[TextFile, ...]) -> list[Finding]:
    findings: list[Finding] = []
    for file in files:
        if Path(file.relative).suffix.lower() not in _TRANSFORM_SUFFIXES:
            continue
        if not (
            file.relative.startswith("pipelines/")
            or file.relative.startswith("src/jobs/")
        ):
            continue
        for line_no, line in enumerate(file.text.splitlines(), start=1):
            stripped = line.lstrip()
            if stripped.startswith("#"):
                continue
            if _SELECT_STAR.search(line):
                findings.append(
                    _fail(
                        "DE-B002",
                        f"{file.relative}:{line_no}",
                        "SELECT * proibido em transformação",
                    )
                )
    return findings


def _check_data_contract(
    project_root: Path,
    files: tuple[TextFile, ...],
) -> list[Finding]:
    contract_candidates = [
        file
        for file in files
        if file.relative.startswith("contracts/")
        or Path(file.relative).name.startswith("data-contract")
    ]
    for file in contract_candidates:
        if _VERSION_FIELD.search(file.text):
            return []

    # também aceita contracts/ como diretório com yaml versionado já coberto acima
    if (project_root / "contracts").is_dir() and not contract_candidates:
        return [
            _fail(
                "DE-B003",
                "contracts/",
                "Diretório contracts/ existe sem contrato versionado legível",
            )
        ]

    return [
        _fail(
            "DE-B003",
            ".",
            "Contrato de dados mínimo versionado ausente (contracts/*.yaml com version)",
        )
    ]
