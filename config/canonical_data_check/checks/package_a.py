"""Checks do pacote A — Universal blockers."""

from __future__ import annotations

import re
from pathlib import Path

from config.canonical_data_check.findings import Finding
from config.canonical_data_check.scanner import TextFile

_SECRET_PATTERNS: tuple[re.Pattern[str], ...] = (
    re.compile(r"(?i)\b(password|passwd|pwd)\s*[:=]\s*['\"][^'\"]+['\"]"),
    re.compile(r'(?i)"(password|passwd|pwd|api[_-]?key|secret)"\s*:\s*"[^"]+"'),
    re.compile(r"(?i)\b(api[_-]?key|access[_-]?key|secret[_-]?key)\s*[:=]\s*['\"][^'\"]+['\"]"),
    re.compile(r"(?i)\b(aws_secret_access_key|private_key)\s*[:=]\s*['\"][^'\"]+['\"]"),
    re.compile(r"-----BEGIN (?:RSA |OPENSSH )?PRIVATE KEY-----"),
    re.compile(r"(?i)(connection[_-]?string|jdbc)\s*[:=]\s*['\"][^'\"]*(password|pwd)=[^'\"]+['\"]"),
)

_DESTRUCTIVE_PATTERN = re.compile(
    r"(?i)\b(DROP\s+TABLE|TRUNCATE\s+TABLE|DELETE\s+FROM)\b"
)
_DESTRUCTIVE_GATE_PATTERN = re.compile(
    r"(?i)(DESTRUCTIVE_GATE|destructive-gate|APPROVED_DESTRUCTIVE|docs/adr/)"
)

_RUN_ID_PATTERN = re.compile(r"(?i)\brun[_-]?id\b")
_LOGGING_PATTERN = re.compile(r"(?i)\b(logging|logger|structured\s*logging)\b")
_OWNER_PATTERN = re.compile(r"(?i)^\s*owner\s*[:=]", re.MULTILINE)


def check_package_a(project_root: Path, files: tuple[TextFile, ...]) -> tuple[Finding, ...]:
    """Executa checks universais A001–A005."""
    findings: list[Finding] = []
    findings.extend(_check_secrets(files))
    findings.extend(_check_destructive(files))
    findings.extend(_check_layout(project_root))
    findings.extend(_check_run_id_logging(files))
    findings.extend(_check_owner(files))
    return tuple(findings)


def _fail(rule_id: str, path: str, message: str) -> Finding:
    return Finding(
        rule_id=rule_id,
        severity="blocker",
        status="fail",
        path=path,
        message=message,
    )


def _check_secrets(files: tuple[TextFile, ...]) -> list[Finding]:
    findings: list[Finding] = []
    for file in files:
        for line_no, line in enumerate(file.text.splitlines(), start=1):
            for pattern in _SECRET_PATTERNS:
                if pattern.search(line):
                    findings.append(
                        _fail(
                            "DE-A001",
                            f"{file.relative}:{line_no}",
                            "Possível secret versionado detectado (valor omitido)",
                        )
                    )
                    break
    return findings


def _check_destructive(files: tuple[TextFile, ...]) -> list[Finding]:
    findings: list[Finding] = []
    for file in files:
        if not _DESTRUCTIVE_PATTERN.search(file.text):
            continue
        if _DESTRUCTIVE_GATE_PATTERN.search(file.text):
            continue
        findings.append(
            _fail(
                "DE-A002",
                file.relative,
                "Operação destrutiva detectada sem gate explícito no arquivo",
            )
        )
    return findings


def _check_layout(project_root: Path) -> list[Finding]:
    has_config = (project_root / "config").is_dir()
    has_pipelines = (project_root / "pipelines").is_dir()
    has_jobs = (project_root / "src" / "jobs").is_dir()
    has_tests = (project_root / "tests").is_dir()
    if has_config and (has_pipelines or has_jobs) and has_tests:
        return []
    missing: list[str] = []
    if not has_config:
        missing.append("config/")
    if not (has_pipelines or has_jobs):
        missing.append("pipelines/ ou src/jobs/")
    if not has_tests:
        missing.append("tests/")
    return [
        _fail(
            "DE-A003",
            ".",
            "Layout mínimo ausente: " + ", ".join(missing),
        )
    ]


def _check_run_id_logging(files: tuple[TextFile, ...]) -> list[Finding]:
    has_run_id = any(_RUN_ID_PATTERN.search(file.text) for file in files)
    has_logging = any(_LOGGING_PATTERN.search(file.text) for file in files)
    if has_run_id and has_logging:
        return []
    missing: list[str] = []
    if not has_run_id:
        missing.append("run_id")
    if not has_logging:
        missing.append("logging")
    return [
        _fail(
            "DE-A004",
            ".",
            "Declaração ausente de: " + ", ".join(missing),
        )
    ]


def _check_owner(files: tuple[TextFile, ...]) -> list[Finding]:
    owner_markers = {
        "OWNER",
        "CODEOWNERS",
        ".harness/data-check/project_profile.yaml",
    }
    for file in files:
        if file.relative in owner_markers or file.relative.endswith("/CODEOWNERS"):
            if file.text.strip():
                return []
            continue
        if _OWNER_PATTERN.search(file.text):
            return []
    return [
        _fail(
            "DE-A005",
            ".",
            "Owner do pipeline não declarado (OWNER, owner: em YAML ou CODEOWNERS)",
        )
    ]
