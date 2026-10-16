"""Checks do pacote E — keyvault-cloud (facade / map / consumidores).

Regras alinhadas ao YAML (applicability ``keyvault-cloud``):

- DE-E001 — facade / ponto único presente
- DE-E002 — map só IDs/URIs (sem literais de secret)
- DE-E003 — consumidores sem SDK vault direto

Applicability: marker ``secret_store`` **ou** auto-detect. ``multi`` = união
OCI+Azure nas superfícies de check. Scan estático; sem API live; findings sem
valor de secret.
"""

from __future__ import annotations

import re
from pathlib import Path

from config.canonical_data_check.de_marker import (
    SECRET_STORE_AZURE,
    SECRET_STORE_MULTI,
    SECRET_STORE_OCI,
    resolve_effective_secret_store,
)
from config.canonical_data_check.findings import Finding
from config.canonical_data_check.scanner import TextFile

_FACADE_PATH = re.compile(
    r"(?:^|/)(?:secrets_facade|vault_facade|cloud_secrets|key_oci|key_azure)"
    r"(?:\.py)?$",
    re.IGNORECASE,
)
_MAP_NAME_TOKENS = ("secrets_map", "secret_map", "vault_map")
_OCI_SDK_IMPORT = re.compile(
    r"(?m)^\s*(?:from\s+oci\.(?:secrets|vault|key_management)\b|"
    r"import\s+oci\.(?:secrets|vault|key_management)\b|"
    r"from\s+oci\s+import\s+[^\n]*\bsecrets\b)",
    re.IGNORECASE,
)
_AZURE_SDK_IMPORT = re.compile(
    r"(?m)^\s*(?:from\s+azure\.keyvault(?:\.\w+)?\b|"
    r"import\s+azure\.keyvault(?:\.\w+)?\b)",
    re.IGNORECASE,
)
_LITERAL_SECRET_IN_MAP = re.compile(
    r"(?i)^\s*[\w.\-]+\s*:\s*['\"]([^'\"]{8,})['\"]\s*(?:#.*)?$",
    re.MULTILINE,
)
_MAP_SUFFIXES = frozenset({".yaml", ".yml", ".json"})
_DUAL_FACADE_TOKENS = ("cloud_secrets", "secrets_facade", "vault_facade")


def check_package_e(
    project_root: Path,
    files: tuple[TextFile, ...],
) -> tuple[Finding, ...]:
    """Executa DE-E001–E003; skip total quando vault não aplica."""
    store = resolve_effective_secret_store(project_root, files=files)
    if store is None:
        return (
            _skip("DE-E001", "Vault cloud ausente — keyvault-cloud não aplicável"),
            _skip("DE-E002", "Vault cloud ausente — keyvault-cloud não aplicável"),
            _skip("DE-E003", "Vault cloud ausente — keyvault-cloud não aplicável"),
        )

    need_oci = store in {SECRET_STORE_OCI, SECRET_STORE_MULTI}
    need_azure = store in {SECRET_STORE_AZURE, SECRET_STORE_MULTI}
    findings: list[Finding] = []
    findings.extend(_check_e001_facade(files, need_oci=need_oci, need_azure=need_azure))
    findings.extend(_check_e002_map(files))
    findings.extend(
        _check_e003_consumers(files, need_oci=need_oci, need_azure=need_azure)
    )
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


def _normalized_relative(file: TextFile) -> str:
    return file.relative.replace("\\", "/")


def _is_facade(file: TextFile) -> bool:
    return bool(_FACADE_PATH.search(_normalized_relative(file)))


def _facade_covers_oci(file: TextFile) -> bool:
    relative_l = _normalized_relative(file).lower()
    return (
        "key_oci" in relative_l
        or any(token in relative_l for token in _DUAL_FACADE_TOKENS)
        or bool(_OCI_SDK_IMPORT.search(file.text))
    )


def _facade_covers_azure(file: TextFile) -> bool:
    relative_l = _normalized_relative(file).lower()
    return (
        "key_azure" in relative_l
        or any(token in relative_l for token in _DUAL_FACADE_TOKENS)
        or bool(_AZURE_SDK_IMPORT.search(file.text))
    )


def _is_secret_map(file: TextFile) -> bool:
    relative = _normalized_relative(file)
    relative_l = relative.lower()
    suffix = Path(relative_l).suffix
    if suffix not in _MAP_SUFFIXES and not relative_l.endswith(".secrets.example"):
        return False
    name = Path(relative_l).name
    if any(token in name for token in _MAP_NAME_TOKENS):
        return True
    return relative_l.startswith("config/") and "secret" in name


def _check_e001_facade(
    files: tuple[TextFile, ...],
    *,
    need_oci: bool,
    need_azure: bool,
) -> list[Finding]:
    facades = tuple(file for file in files if _is_facade(file))
    if not facades:
        return [
            _fail(
                "DE-E001",
                ".",
                "Facade/ponto único de secret ausente (key_oci/key_azure/secrets_facade)",
            )
        ]

    has_oci = any(_facade_covers_oci(file) for file in facades)
    has_azure = any(_facade_covers_azure(file) for file in facades)

    if need_oci and need_azure:
        if has_oci and has_azure:
            return []
        return [
            _fail(
                "DE-E001",
                facades[0].relative,
                "secret_store multi exige facade cobrindo OCI e Azure (união)",
            )
        ]
    if need_oci and not has_oci:
        return [
            _fail(
                "DE-E001",
                facades[0].relative,
                "Facade OCI ausente para secret_store=oci",
            )
        ]
    if need_azure and not has_azure:
        return [
            _fail(
                "DE-E001",
                facades[0].relative,
                "Facade Azure ausente para secret_store=azure",
            )
        ]
    return []


def _check_e002_map(files: tuple[TextFile, ...]) -> list[Finding]:
    maps = tuple(file for file in files if _is_secret_map(file))
    if not maps:
        return [
            _fail(
                "DE-E002",
                ".",
                "Map de secrets ausente (secrets_map com IDs/URIs apenas)",
            )
        ]

    for file in maps:
        if _map_contains_literal_secret(file.text):
            return [
                _fail(
                    "DE-E002",
                    file.relative,
                    "Map de secrets contém possível valor literal (use OCID/URI/placeholder)",
                )
            ]
    return []


def _map_contains_literal_secret(text: str) -> bool:
    for match in _LITERAL_SECRET_IN_MAP.finditer(text):
        value = match.group(1).strip()
        lowered = value.lower()
        if lowered.startswith(
            ("ocid1.", "https://", "placeholder", "<", "${")
        ):
            continue
        return True
    return False


def _check_e003_consumers(
    files: tuple[TextFile, ...],
    *,
    need_oci: bool,
    need_azure: bool,
) -> list[Finding]:
    for file in files:
        if Path(file.relative).suffix.lower() != ".py":
            continue
        if _is_facade(file):
            continue
        if need_oci and _OCI_SDK_IMPORT.search(file.text):
            return [
                _fail(
                    "DE-E003",
                    file.relative,
                    "Consumidor importa SDK OCI Vault — use o facade",
                )
            ]
        if need_azure and _AZURE_SDK_IMPORT.search(file.text):
            return [
                _fail(
                    "DE-E003",
                    file.relative,
                    "Consumidor importa SDK Azure Key Vault — use o facade",
                )
            ]
    return []
