"""Checks do pacote C — Airflow condicional."""

from __future__ import annotations

import re
from pathlib import Path

from config.canonical_data_check.findings import Finding
from config.canonical_data_check.scanner import TextFile

_AIRFLOW_IMPORT = re.compile(
    r"(?i)^\s*(from\s+airflow\b|import\s+airflow\b)",
    re.MULTILINE,
)
_TAGS_PATTERN = re.compile(r"(?i)\btags\s*=")
_PHASE_PRE = re.compile(r"(?i)\b(pre[_-]?process|prepare|extract|pré|pre)\b")
_PHASE_LOAD = re.compile(r"(?i)\b(load|carga|ingest)\b")
_PHASE_POST = re.compile(r"(?i)\b(post[_-]?process|validate|pós|post)\b")
_SPARK_CONF_REF = re.compile(r"(?i)spark\.conf|config/spark\.conf")


def detect_airflow(project_root: Path, files: tuple[TextFile, ...]) -> bool:
    """Detecta presença de Airflow/DAG no projeto."""
    if (project_root / "dags").is_dir():
        if any((project_root / "dags").rglob("*.py")):
            return True
    if (project_root / "airflow.cfg").is_file():
        return True
    for file in files:
        if file.relative.endswith(".py") and _AIRFLOW_IMPORT.search(file.text):
            return True
        if "apache-airflow" in file.text.lower() and file.relative.endswith(
            ("requirements.txt", "pyproject.toml")
        ):
            return True
    return False


def check_package_c(
    project_root: Path,
    files: tuple[TextFile, ...],
) -> tuple[Finding, ...]:
    """Executa C001–C003 ou emite SKIP quando Airflow/DAG ausente."""
    if not detect_airflow(project_root, files):
        return tuple(
            Finding(
                rule_id=rule_id,
                severity="blocker",
                status="skip",
                path=".",
                message="Airflow/DAG não detectado — pacote C não aplicável",
            )
            for rule_id in ("DE-C001", "DE-C002", "DE-C003")
        )

    dag_files = _dag_files(project_root, files)
    findings: list[Finding] = []
    findings.extend(_check_tags(dag_files))
    findings.extend(_check_phases(dag_files))
    findings.extend(_check_spark_conf(project_root, dag_files))
    return tuple(findings)


def _dag_files(project_root: Path, files: tuple[TextFile, ...]) -> tuple[TextFile, ...]:
    selected: list[TextFile] = []
    for file in files:
        if not file.relative.endswith(".py"):
            continue
        under_dags = file.relative.startswith("dags/")
        imports_airflow = bool(_AIRFLOW_IMPORT.search(file.text))
        if under_dags or imports_airflow:
            selected.append(file)
    if selected:
        return tuple(selected)
    # fallback: qualquer py sob dags já coberto; se detectou por airflow.cfg vazio
    return tuple()


def _fail(rule_id: str, path: str, message: str) -> Finding:
    return Finding(
        rule_id=rule_id,
        severity="blocker",
        status="fail",
        path=path,
        message=message,
    )


def _check_tags(dag_files: tuple[TextFile, ...]) -> list[Finding]:
    if any(_TAGS_PATTERN.search(file.text) for file in dag_files):
        return []
    path = dag_files[0].relative if dag_files else "dags/"
    return [_fail("DE-C001", path, "DAG sem tags declaradas")]


def _check_phases(dag_files: tuple[TextFile, ...]) -> list[Finding]:
    combined = "\n".join(file.text for file in dag_files)
    has_pre = bool(_PHASE_PRE.search(combined))
    has_load = bool(_PHASE_LOAD.search(combined))
    has_post = bool(_PHASE_POST.search(combined))
    if has_pre and has_load and has_post:
        return []
    path = dag_files[0].relative if dag_files else "dags/"
    return [
        _fail(
            "DE-C002",
            path,
            "DAG não separa fases pré/carga/pós de forma explícita",
        )
    ]


def _check_spark_conf(
    project_root: Path,
    dag_files: tuple[TextFile, ...],
) -> list[Finding]:
    spark_conf = project_root / "config" / "spark.conf"
    referenced = any(_SPARK_CONF_REF.search(file.text) for file in dag_files)
    if spark_conf.is_file() and referenced:
        return []
    path = dag_files[0].relative if dag_files else "config/spark.conf"
    if not spark_conf.is_file():
        return [
            _fail(
                "DE-C003",
                "config/spark.conf",
                "config/spark.conf ausente para submit versionado",
            )
        ]
    return [
        _fail(
            "DE-C003",
            path,
            "DAG não referencia config/spark.conf no spark-submit",
        )
    ]
