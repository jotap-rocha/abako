"""Motor de validação — resolve perfil e despacha pacotes pelo registry."""

from __future__ import annotations

from pathlib import Path

from config.canonical_data_check.checks import PACKAGE_CHECK_REGISTRY
from config.canonical_data_check.constants import (
    DEFAULT_PROFILE,
    EXIT_BLOCKERS,
    EXIT_OK,
    EXIT_USAGE,
)
from config.canonical_data_check.de_marker import (
    resolve_effective_profile,
    resolve_effective_secret_store,
)
from config.canonical_data_check.findings import (
    Finding,
    ValidationResult,
    sort_findings,
)
from config.canonical_data_check.scanner import iter_text_files
from config.data_engineering import DataEngineeringContract


def validate_project(
    project_path: Path | str,
    *,
    contract_path: Path | str | None = None,
    profile: str = DEFAULT_PROFILE,
) -> ValidationResult:
    """Valida um path de projeto contra a norma DE.

    Exit codes:
      0 — sem blockers (SKIP de C não falha)
      1 — findings blocker com status fail
      2 — path/contrato inválidos (erro de uso/config)

    Pacote E (keyvault-cloud) é ortogonal ao perfil: injeta-se quando
    ``secret_store`` (marker) ou auto-detect vault aplica.
    """
    root = Path(project_path)
    if not root.exists() or not root.is_dir():
        return ValidationResult(
            exit_code=EXIT_USAGE,
            findings=(
                Finding(
                    rule_id="DE-USAGE",
                    severity="blocker",
                    status="fail",
                    path=str(project_path),
                    message="Path de projeto inexistente ou não é diretório",
                ),
            ),
            profile=profile,
        )

    resolved_contract = (
        Path(contract_path)
        if contract_path is not None
        else default_contract_path()
    )
    try:
        contract = DataEngineeringContract.load(resolved_contract)
        files = iter_text_files(root)
        effective_profile = resolve_effective_profile(
            root,
            valid_profiles=frozenset(item.id for item in contract.profiles),
            fallback_profile=profile,
            files=files,
        )
        selected_profile = contract.profile(effective_profile)
    except (OSError, ValueError, KeyError) as exc:
        return ValidationResult(
            exit_code=EXIT_USAGE,
            findings=(
                Finding(
                    rule_id="DE-USAGE",
                    severity="blocker",
                    status="fail",
                    path=str(resolved_contract),
                    message=f"Falha ao carregar contrato/perfil: {exc}",
                ),
            ),
            profile=profile,
        )

    package_ids = list(selected_profile.package_ids)
    if (
        resolve_effective_secret_store(root, files=files) is not None
        and "E" not in package_ids
    ):
        package_ids.append("E")

    findings: list[Finding] = []
    for package_id in package_ids:
        checker = PACKAGE_CHECK_REGISTRY.get(package_id)
        if checker is None:
            return ValidationResult(
                exit_code=EXIT_USAGE,
                findings=(
                    Finding(
                        rule_id="DE-USAGE",
                        severity="blocker",
                        status="fail",
                        path=str(resolved_contract),
                        message=f"Pacote sem handler registrado: {package_id}",
                    ),
                ),
                profile=effective_profile,
            )
        findings.extend(checker(root, files))

    ordered = sort_findings(findings)
    has_blocker = any(
        finding.status == "fail" and finding.severity == "blocker"
        for finding in ordered
    )
    return ValidationResult(
        exit_code=EXIT_BLOCKERS if has_blocker else EXIT_OK,
        findings=ordered,
        profile=effective_profile,
    )


def default_contract_path() -> Path:
    """Retorna a fonte normativa padrão na raiz do canônico."""
    return Path(__file__).resolve().parents[2] / "data-engineering.yaml"
