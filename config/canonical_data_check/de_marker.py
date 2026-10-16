"""Marker, auto-detecção Databricks/vault e resolução do perfil efetivo.

Heurísticas estáticas e conservadoras, sem API ou credenciais Databricks:

- DAB: ``databricks.yml|yaml`` ou ``bundle*.yml|yaml`` em qualquer diretório;
- DLT: path/arquivo com token ``dlt`` ou código Python com import/decorator ``dlt``;
- SDP: path/arquivo com token ``sdp`` ou código Python com
  ``pyspark.pipelines``/decorator exatamente ``@dp.``.

Limite MVP conhecido: ``import dlt`` também pode ser a biblioteca dltHub e, sem
outro contexto, gerar falso positivo DLT. O refinamento fica fora da Task 18.

O marker ``.harness/data-check/project_profile.yaml`` é override quando declara
um perfil conhecido. Sem override, SDP+DLT resolve ``databricks-multi``; um único
sinal resolve seu perfil específico; DAB isolado é detectado, mas não escolhe entre
SDP e DLT. Sem sinal de pipeline cloud, preserva o perfil Loop 1 informado.

Campo ortogonal ``secret_store: oci|azure|multi`` (marker) vence auto-detect de
vault. Auto-detect: sinais OCI Vault / Azure Key Vault no filesystem; ambos →
``multi`` (união). Sem sinal e sem marker → vault não aplica.

``/validar`` (via ``data_check_validate_argv`` / ``should_run_data_check``) dispara
data-check com marker **ou** sinal útil SDP/DLT **ou** vault (``secret_store`` /
auto-detect); DAB isolado sem vault não ativa. A raiz deste framework canônico é
reconhecida por sentinel próprio e não ativa apenas por conter fixtures e
referências internas.
"""

from __future__ import annotations

import re
import sys
from collections.abc import Collection
from dataclasses import dataclass
from pathlib import Path

from config.canonical_data_check.constants import DATA_CHECK_DIRNAME, DEFAULT_PROFILE
from config.canonical_data_check.scanner import TextFile, iter_text_files
from config.data_engineering.yaml_loader import MinimalYamlError, load_mapping

DE_PROFILE_MARKER_NAME = "project_profile.yaml"
DE_PROFILE_MARKER = Path(DATA_CHECK_DIRNAME) / DE_PROFILE_MARKER_NAME
DATABRICKS_SDP_PROFILE = "databricks-sdp-medallion"
DATABRICKS_DLT_PROFILE = "databricks-dlt-legacy"
DATABRICKS_MULTI_PROFILE = "databricks-multi"

SECRET_STORE_OCI = "oci"
SECRET_STORE_AZURE = "azure"
SECRET_STORE_MULTI = "multi"
VALID_SECRET_STORES = frozenset(
    {SECRET_STORE_OCI, SECRET_STORE_AZURE, SECRET_STORE_MULTI}
)

DAB_MANIFEST_NAMES = frozenset({"databricks.yml", "databricks.yaml"})
DAB_BUNDLE_SUFFIXES = frozenset({".yml", ".yaml"})

_TOKEN_DLT = re.compile(r"(?:^|[._/-])dlt(?:[._/-]|$)", re.IGNORECASE)
_TOKEN_SDP = re.compile(r"(?:^|[._/-])sdp(?:[._/-]|$)", re.IGNORECASE)
_DLT_CODE = re.compile(
    r"(?m)^\s*(?:import\s+dlt\b|from\s+dlt\b)|@\s*dlt\.",
    re.IGNORECASE,
)
_SDP_CODE = re.compile(
    r"(?m)^\s*(?:from\s+pyspark\s+import\s+pipelines\b|"
    r"from\s+pyspark\.pipelines\b|import\s+pyspark\.pipelines\b)|"
    r"^\s*@dp\.",
    re.IGNORECASE,
)

_OCI_PATH = re.compile(
    r"(?:^|/)(?:key_oci|oci_vault|oci[_-]secrets?)(?:/|\.|$)",
    re.IGNORECASE,
)
_OCI_IMPORT = re.compile(
    r"(?m)^\s*(?:from\s+oci\.(?:secrets|vault|key_management)\b|"
    r"import\s+oci\.(?:secrets|vault|key_management)\b|"
    r"from\s+oci\s+import\s+[^\n]*\bsecrets\b)",
    re.IGNORECASE,
)
_OCID_VAULT_SECRET = re.compile(r"ocid1\.vaultsecret\.", re.IGNORECASE)

_AZURE_PATH = re.compile(
    r"(?:^|/)(?:key_azure|azure[_-]keyvault|azure[_-]vault)(?:/|\.|$)",
    re.IGNORECASE,
)
_AZURE_IMPORT = re.compile(
    r"(?m)^\s*(?:from\s+azure\.keyvault(?:\.\w+)?\b|"
    r"import\s+azure\.keyvault(?:\.\w+)?\b)",
    re.IGNORECASE,
)
_AZURE_VAULT_URI = re.compile(
    r"https://[a-z0-9-]+\.vault\.azure\.net\b",
    re.IGNORECASE,
)


@dataclass(frozen=True, slots=True)
class DatabricksSignals:
    """Sinais Databricks encontrados no filesystem do projeto."""

    dab: bool = False
    dlt: bool = False
    sdp: bool = False

    @property
    def any(self) -> bool:
        """True quando ao menos um sinal Databricks foi detectado."""
        return self.dab or self.dlt or self.sdp

    @property
    def useful_pipeline(self) -> bool:
        """True quando há SDP e/ou DLT — sinal útil para perfil cloud e `/validar`.

        DAB isolado não entra: detecta bundle, mas não escolhe SDP vs DLT nem
        ativa data-check sem marker / sem pipeline cloud.
        """
        return self.sdp or self.dlt


@dataclass(frozen=True, slots=True)
class VaultSignals:
    """Sinais de OCI Vault / Azure Key Vault no filesystem (sem API live)."""

    oci: bool = False
    azure: bool = False

    @property
    def any(self) -> bool:
        """True quando ao menos um cofre cloud foi detectado."""
        return self.oci or self.azure


def has_de_marker(project_root: Path | str) -> bool:
    """True se existir o marker/perfil DE no root do projeto."""
    root = Path(project_root).resolve()
    return (root / DE_PROFILE_MARKER).is_file()


def detect_databricks_signals(
    project_root: Path | str,
    *,
    files: tuple[TextFile, ...] | None = None,
) -> DatabricksSignals:
    """Detecta DAB, DLT e SDP usando somente arquivos locais versionáveis."""
    root = Path(project_root).resolve()
    if not root.is_dir():
        return DatabricksSignals()
    scanned_files = files if files is not None else iter_text_files(root)
    return _signals_from_files(scanned_files)


def detect_vault_signals(
    project_root: Path | str,
    *,
    files: tuple[TextFile, ...] | None = None,
) -> VaultSignals:
    """Detecta sinais OCI Vault / Azure Key Vault no filesystem (conservador)."""
    root = Path(project_root).resolve()
    if not root.is_dir():
        return VaultSignals()
    scanned_files = files if files is not None else iter_text_files(root)
    return _vault_signals_from_files(scanned_files)


def _signals_from_files(files: tuple[TextFile, ...]) -> DatabricksSignals:
    dab = False
    dlt = False
    sdp = False
    for file in files:
        relative = file.relative.lower()
        name = file.path.name.lower()
        dab = dab or is_dab_manifest(name)
        dlt = dlt or bool(_TOKEN_DLT.search(relative) or _DLT_CODE.search(file.text))
        sdp = sdp or bool(_TOKEN_SDP.search(relative) or _SDP_CODE.search(file.text))
        if dab and dlt and sdp:
            break
    return DatabricksSignals(dab=dab, dlt=dlt, sdp=sdp)


def _vault_signals_from_files(files: tuple[TextFile, ...]) -> VaultSignals:
    oci = False
    azure = False
    for file in files:
        relative = file.relative
        text = file.text
        oci = oci or bool(
            _OCI_PATH.search(relative)
            or _OCI_IMPORT.search(text)
            or _OCID_VAULT_SECRET.search(text)
        )
        azure = azure or bool(
            _AZURE_PATH.search(relative)
            or _AZURE_IMPORT.search(text)
            or _AZURE_VAULT_URI.search(text)
        )
        if oci and azure:
            break
    return VaultSignals(oci=oci, azure=azure)


def is_dab_manifest(name: str) -> bool:
    """True para nomes de manifestos DAB reconhecidos pelo detector."""
    if name in DAB_MANIFEST_NAMES:
        return True
    path = Path(name)
    return name.startswith("bundle") and path.suffix in DAB_BUNDLE_SUFFIXES


def read_profile_override(
    project_root: Path | str,
    *,
    valid_profiles: Collection[str],
) -> str | None:
    """Lê o override do marker; perfil ausente/inválido não prevalece."""
    marker = Path(project_root).resolve() / DE_PROFILE_MARKER
    if not marker.is_file():
        return None
    try:
        payload = load_mapping(marker)
    except (OSError, MinimalYamlError):
        return None
    profile = payload.get("profile")
    if not isinstance(profile, str):
        return None
    normalized = profile.strip()
    return normalized if normalized in valid_profiles else None


def read_secret_store_override(project_root: Path | str) -> str | None:
    """Lê ``secret_store`` do marker; valor ausente/inválido não prevalece."""
    marker = Path(project_root).resolve() / DE_PROFILE_MARKER
    if not marker.is_file():
        return None
    try:
        payload = load_mapping(marker)
    except (OSError, MinimalYamlError):
        return None
    store = payload.get("secret_store")
    if not isinstance(store, str):
        return None
    normalized = store.strip().lower()
    return normalized if normalized in VALID_SECRET_STORES else None


def resolve_effective_secret_store(
    project_root: Path | str,
    *,
    files: tuple[TextFile, ...] | None = None,
) -> str | None:
    """Resolve marker ``secret_store`` > auto-detect (oci/azure/multi) > None."""
    override = read_secret_store_override(project_root)
    if override is not None:
        return override

    signals = detect_vault_signals(project_root, files=files)
    if signals.oci and signals.azure:
        return SECRET_STORE_MULTI
    if signals.oci:
        return SECRET_STORE_OCI
    if signals.azure:
        return SECRET_STORE_AZURE
    return None


def resolve_effective_profile(
    project_root: Path | str,
    *,
    valid_profiles: Collection[str],
    fallback_profile: str = DEFAULT_PROFILE,
    files: tuple[TextFile, ...] | None = None,
) -> str:
    """Resolve marker > SDP/DLT detectado > fallback Loop 1/CLI."""
    override = read_profile_override(
        project_root,
        valid_profiles=valid_profiles,
    )
    if override is not None:
        return override

    signals = detect_databricks_signals(project_root, files=files)
    if signals.sdp and signals.dlt:
        return DATABRICKS_MULTI_PROFILE
    if signals.sdp:
        return DATABRICKS_SDP_PROFILE
    if signals.dlt:
        return DATABRICKS_DLT_PROFILE
    return fallback_profile


def is_canonical_harness_root(project_root: Path | str) -> bool:
    """Reconhece conservadoramente a raiz deste framework canônico.

    A conjunção evita classificar um projeto-filho apenas por possuir um dos
    artefatos propagados pelo install-harness.
    """
    root = Path(project_root).resolve()
    return (
        (root / "data-engineering.yaml").is_file()
        and (root / "config" / "canonical_data_check").is_dir()
        and (root / "CLAUDE.md").is_file()
        and (root / "AGENTS.md").is_file()
    )


def should_run_data_check(
    project_root: Path | str,
    *,
    files: tuple[TextFile, ...] | None = None,
) -> bool:
    """True se `/validar` deve invocar o data-check.

    Ativa com marker DE **ou** auto-detect de pipeline cloud útil (SDP e/ou DLT)
    **ou** vault cloud (marker ``secret_store`` / auto-detect OCI|Azure).
    DAB isolado sem vault não ativa. O root canônico, reconhecido por sentinel
    específico, não ativa por seus próprios artefatos internos.
    """
    root = Path(project_root).resolve()
    if has_de_marker(root):
        return True
    if is_canonical_harness_root(root):
        return False
    scanned = files if files is not None else None
    if detect_databricks_signals(root, files=scanned).useful_pipeline:
        return True
    return resolve_effective_secret_store(root, files=scanned) is not None


def data_check_validate_argv(
    project_root: Path | str,
    *,
    files: tuple[TextFile, ...] | None = None,
) -> list[str] | None:
    """Argv para `validate` quando o gate DE deve rodar; caso contrário ``None``.

    Fonte única para `/validar` — não reimplementar a heurística em shell.
    Retornar ``None`` significa: `/validar` **não** deve invocar o data-check.
    """
    root = Path(project_root).resolve()
    if not should_run_data_check(root, files=files):
        return None
    return [
        sys.executable,
        "-m",
        "config.canonical_data_check",
        "validate",
        str(root),
    ]
