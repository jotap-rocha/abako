"""Checks do pacote D — Databricks cloud (SDP/DLT/DAB/UC em filesystem).

Regras condicionais alinhadas ao YAML:

- DE-D001 — ``databricks-dab-present``
- DE-D002 — ``sdp-signal-present``
- DE-D003 — ``dlt-signal-present``
- DE-D004 / DE-D005 — ``databricks-cloud`` (sempre que o pacote D roda)

Scan estático e determinístico. Sem API live, sem credenciais e sem logar
conteúdo sensível — findings expõem ``rule_id``, ``path`` e mensagem genérica.
"""

from __future__ import annotations

import re
from pathlib import Path

from config.canonical_data_check.de_marker import (
    DatabricksSignals,
    detect_databricks_signals,
    is_dab_manifest,
)
from config.canonical_data_check.findings import Finding
from config.canonical_data_check.scanner import TextFile

_LAYER_TOKENS = ("bronze", "silver", "gold", "medallion")
_AUDITABLE_IDENTITY = re.compile(
    r"(?i)^[ \t]*(owner|run_as|run[_-]?identity|service[_-]?principal"
    r"|service[_-]?principal[_-]?name)[ \t]*:[ \t]*"
    r"(?:['\"][^'\"\r\n]+['\"]|[^\s#'\"\r\n][^#\r\n]*)"
    r"[ \t]*(?:#.*)?$",
    re.MULTILINE,
)
_QUARANTINE = re.compile(r"(?i)\bquarantine(?:[_-]?\w+)?\b")
_SCHEMA_RESCUE = re.compile(r"(?i)\bschema[_-]?rescue\b")
_FAIL_POLICY = re.compile(r"(?i)\b(fail|on_drift\s*:\s*fail)\b")
_QUARANTINE_POLICY = re.compile(r"(?i)\b(quarantine|on_drift\s*:\s*quarantine)\b")
_GRANTS = re.compile(
    r"(?i)\b(grants?|privileges?|grant\s+(select|modify|all)|revoke\b)\b"
)
_LINEAGE = re.compile(r"(?i)\b(lineage|linhagem)\b")
_POLICY_SUFFIXES = frozenset({".yaml", ".yml", ".sql", ".md", ".json"})


def check_package_d(
    project_root: Path,
    files: tuple[TextFile, ...],
) -> tuple[Finding, ...]:
    """Executa DE-D001–D005 com skip condicional por sinal SDP/DLT/DAB."""
    signals = detect_databricks_signals(project_root, files=files)
    findings: list[Finding] = []
    findings.extend(_check_d001_dab(signals, files))
    findings.extend(_check_d002_sdp(project_root, signals, files))
    findings.extend(_check_d003_dlt(signals, files))
    findings.extend(_check_d004_schema_rescue(files))
    findings.extend(_check_d005_uc_fs(files))
    return tuple(findings)


def _skip(rule_id: str, message: str) -> Finding:
    return Finding(
        rule_id=rule_id,
        severity="blocker",
        status="skip",
        path=".",
        message=message,
    )


def _fail(rule_id: str, path: str, message: str) -> Finding:
    return Finding(
        rule_id=rule_id,
        severity="blocker",
        status="fail",
        path=path,
        message=message,
    )


def _check_d001_dab(
    signals: DatabricksSignals,
    files: tuple[TextFile, ...],
) -> list[Finding]:
    if not signals.dab:
        return [
            _skip(
                "DE-D001",
                "Sinal DAB/job ausente — regra databricks-dab-present não aplicável",
            )
        ]

    dab_files = tuple(file for file in files if _is_dab_file(file))
    if any(_AUDITABLE_IDENTITY.search(file.text) for file in dab_files):
        return []

    path = dab_files[0].relative if dab_files else "databricks.yml"
    return [
        _fail(
            "DE-D001",
            path,
            "Bundle/job Databricks sem owner ou run identity auditável",
        )
    ]


def _is_dab_file(file: TextFile) -> bool:
    return is_dab_manifest(Path(file.relative).name.lower())


def _check_d002_sdp(
    project_root: Path,
    signals: DatabricksSignals,
    files: tuple[TextFile, ...],
) -> list[Finding]:
    if not signals.sdp:
        return [
            _skip(
                "DE-D002",
                "Sinal SDP ausente — regra sdp-signal-present não aplicável",
            )
        ]

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
        relative_l = file.relative.lower()
        describes_sdp_layout = (
            relative_l.startswith("config/")
            or "sdp" in relative_l
            or "medallion" in relative_l
        )
        if describes_sdp_layout and all(
            token in lowered for token in ("bronze", "silver", "gold")
        ):
            return []

    return [
        _fail(
            "DE-D002",
            ".",
            "Pipeline SDP sem camadas medallion explícitas (bronze/silver/gold)",
        )
    ]


def _check_d003_dlt(
    signals: DatabricksSignals,
    files: tuple[TextFile, ...],
) -> list[Finding]:
    if not signals.dlt:
        return [
            _skip(
                "DE-D003",
                "Sinal DLT ausente — regra dlt-signal-present não aplicável",
            )
        ]

    dlt_files = tuple(file for file in files if _is_dlt_source(file))
    policy_files = tuple(file for file in files if _is_quality_policy(file))
    candidates = dlt_files + policy_files
    has_quarantine = any(_QUARANTINE.search(file.text) for file in candidates)
    if has_quarantine:
        return []

    path = dlt_files[0].relative if dlt_files else "."
    return [
        _fail(
            "DE-D003",
            path,
            "Pipeline DLT sem destino/política de quarentena versionada",
        )
    ]


def _is_dlt_source(file: TextFile) -> bool:
    if Path(file.relative).suffix.lower() != ".py":
        return False
    relative_l = file.relative.lower()
    text_l = file.text.lower()
    return (
        "dlt" in relative_l
        or "import dlt" in text_l
        or "from dlt" in text_l
        or "@dlt." in text_l
    )


def _is_quality_policy(file: TextFile) -> bool:
    """Limita D003 a policies/config versionados, sem inspecionar dados."""
    relative_l = file.relative.lower()
    suffix = Path(relative_l).suffix
    under_policy_root = relative_l.startswith("policies/") or "/policies/" in relative_l
    named_quality_policy = (
        relative_l.startswith("config/")
        and any(token in relative_l for token in ("quality", "quarantine", "dlt-policy"))
    )
    return (under_policy_root or named_quality_policy) and suffix in _POLICY_SUFFIXES


def _check_d004_schema_rescue(files: tuple[TextFile, ...]) -> list[Finding]:
    for file in files:
        if Path(file.relative).suffix.lower() not in _POLICY_SUFFIXES:
            continue
        relative_l = file.relative.lower()
        mentions_policy = bool(_SCHEMA_RESCUE.search(file.text)) or (
            "schema-rescue" in relative_l or "schema_rescue" in relative_l
        )
        if not mentions_policy:
            continue
        text = file.text
        documents_choice = (
            (_FAIL_POLICY.search(text) is not None and _QUARANTINE_POLICY.search(text) is not None)
            or re.search(r"(?i)on_drift\s*:\s*(fail|quarantine)\b", text) is not None
        )
        if documents_choice:
            return []

    return [
        _fail(
            "DE-D004",
            ".",
            "Schema rescue policy ausente (documentar fail vs quarantine)",
        )
    ]


def _check_d005_uc_fs(files: tuple[TextFile, ...]) -> list[Finding]:
    has_grants = False
    has_lineage = False
    grant_path = "."
    lineage_path = "."

    for file in files:
        suffix = Path(file.relative).suffix.lower()
        if suffix not in _POLICY_SUFFIXES:
            continue
        relative_l = file.relative.lower()
        text = file.text
        grants_hit = bool(_GRANTS.search(text)) or "grant" in relative_l
        lineage_hit = bool(_LINEAGE.search(text)) or "lineage" in relative_l or "linhagem" in relative_l
        if grants_hit:
            has_grants = True
            grant_path = file.relative
        if lineage_hit:
            has_lineage = True
            lineage_path = file.relative
        if has_grants and has_lineage:
            return []

    if not has_grants and not has_lineage:
        return [
            _fail(
                "DE-D005",
                ".",
                "Grants e linhagem Unity Catalog ausentes no filesystem",
            )
        ]
    if not has_grants:
        return [
            _fail(
                "DE-D005",
                lineage_path,
                "Grants Unity Catalog ausentes no filesystem",
            )
        ]
    return [
        _fail(
            "DE-D005",
            grant_path,
            "Linhagem Unity Catalog ausente no filesystem",
        )
    ]
