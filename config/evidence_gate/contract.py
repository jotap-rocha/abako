"""Contrato tipado e imutável de evidence-gate (collect/check por task)."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Mapping

from config.evidence_gate.yaml_loader import load_mapping


@dataclass(frozen=True, slots=True)
class EvidenceLimits:
    """Caps e política de falha do collect (G1/G3)."""

    max_log_bytes: int
    collect_time_factor: int
    fail_on_exceed: bool
    hard_timeout_seconds: int | None


@dataclass(frozen=True, slots=True)
class ManifestSchema:
    """Campos obrigatórios do manifesto por task."""

    required_fields: tuple[str, ...]
    criterion_required: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class CheckRules:
    """Regras mecânicas do ``check``."""

    require_exit_zero: bool
    require_log_exists: bool
    require_test_path_or_waiver: bool
    require_evidencias_ref: bool


@dataclass(frozen=True, slots=True)
class EvidencePaths:
    """Nomes relativos sob a raiz ``evidencias/``."""

    tasks_dir: str
    logs_dir: str
    audit_file: str


@dataclass(frozen=True, slots=True)
class EvidenceGateContract:
    """Fonte normativa carregada de ``evidence-gate.yaml``."""

    version: int
    limits: EvidenceLimits
    manifest: ManifestSchema
    check: CheckRules
    paths: EvidencePaths

    @classmethod
    def load(cls, path: Path | str) -> EvidenceGateContract:
        """Carrega e valida o contrato a partir de um path YAML."""
        return cls.from_mapping(load_mapping(Path(path)))

    @classmethod
    def from_mapping(cls, data: Mapping[str, object]) -> EvidenceGateContract:
        """Valida um mapping no boundary e cria o contrato imutável."""
        version = _require_positive_int(data, "version", "version")
        limits = _build_limits(_require_non_empty_mapping(data, "limits", "limits"))
        manifest = _build_manifest(
            _require_non_empty_mapping(data, "manifest", "manifest")
        )
        check = _build_check(_require_non_empty_mapping(data, "check", "check"))
        paths_raw = data.get("paths")
        if paths_raw is None:
            paths = EvidencePaths(
                tasks_dir="tasks",
                logs_dir="logs",
                audit_file="audit.jsonl",
            )
        else:
            paths = _build_paths(_as_mapping(paths_raw, "paths"))
        return cls(
            version=version,
            limits=limits,
            manifest=manifest,
            check=check,
            paths=paths,
        )


def _build_limits(data: Mapping[str, object]) -> EvidenceLimits:
    max_log = _require_positive_int(data, "max_log_bytes", "limits.max_log_bytes")
    factor = _require_positive_int(
        data, "collect_time_factor", "limits.collect_time_factor"
    )
    fail_on = _require_bool(data, "fail_on_exceed", "limits.fail_on_exceed")
    hard = data.get("hard_timeout_seconds")
    if hard is not None:
        raise ValueError(
            "limits.hard_timeout_seconds deve ser omitido ou null "
            "(G1 — sem hard timeout no contrato; só collect_time_factor)"
        )
    return EvidenceLimits(
        max_log_bytes=max_log,
        collect_time_factor=factor,
        fail_on_exceed=fail_on,
        hard_timeout_seconds=hard,
    )


def _build_manifest(data: Mapping[str, object]) -> ManifestSchema:
    required = _require_string_list(
        data, "required_fields", "manifest.required_fields"
    )
    criterion = _require_string_list(
        data, "criterion_required", "manifest.criterion_required"
    )
    for needed in ("task_id", "criteria"):
        if needed not in required:
            raise ValueError(
                f"manifest.required_fields deve incluir '{needed}'"
            )
    if "id" not in criterion or "command" not in criterion:
        raise ValueError(
            "manifest.criterion_required deve incluir 'id' e 'command'"
        )
    return ManifestSchema(required_fields=required, criterion_required=criterion)


def _build_check(data: Mapping[str, object]) -> CheckRules:
    return CheckRules(
        require_exit_zero=_require_bool(
            data, "require_exit_zero", "check.require_exit_zero"
        ),
        require_log_exists=_require_bool(
            data, "require_log_exists", "check.require_log_exists"
        ),
        require_test_path_or_waiver=_require_bool(
            data,
            "require_test_path_or_waiver",
            "check.require_test_path_or_waiver",
        ),
        require_evidencias_ref=_require_bool(
            data,
            "require_evidencias_ref",
            "check.require_evidencias_ref",
        ),
    )


def _build_paths(data: Mapping[str, object]) -> EvidencePaths:
    return EvidencePaths(
        tasks_dir=_require_string(data, "tasks_dir", "paths.tasks_dir"),
        logs_dir=_require_string(data, "logs_dir", "paths.logs_dir"),
        audit_file=_require_string(data, "audit_file", "paths.audit_file"),
    )


def _as_mapping(value: object, path: str) -> Mapping[str, object]:
    if not isinstance(value, dict):
        raise ValueError(f"{path} deve ser mapping")
    if not all(isinstance(key, str) for key in value):
        raise ValueError(f"{path} deve ter somente chaves string")
    return value


def _require_non_empty_mapping(
    data: Mapping[str, object],
    key: str,
    path: str,
) -> Mapping[str, object]:
    mapping = _as_mapping(data.get(key), path)
    if not mapping:
        raise ValueError(f"{path} deve ser mapping não vazio")
    return mapping


def _require_string(data: Mapping[str, object], key: str, path: str) -> str:
    value = data.get(key)
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{path} deve ser string não vazia")
    return value.strip()


def _require_string_list(
    data: Mapping[str, object],
    key: str,
    path: str,
) -> tuple[str, ...]:
    value = data.get(key)
    if not isinstance(value, list) or not value:
        raise ValueError(f"{path} deve ser lista não vazia")
    if not all(isinstance(item, str) and item.strip() for item in value):
        raise ValueError(f"{path} deve conter somente strings não vazias")
    return tuple(item.strip() for item in value)


def _require_positive_int(data: Mapping[str, object], key: str, path: str) -> int:
    value = data.get(key)
    if not isinstance(value, int) or isinstance(value, bool) or value < 1:
        raise ValueError(f"{path} deve ser inteiro positivo")
    return value


def _require_bool(data: Mapping[str, object], key: str, path: str) -> bool:
    value = data.get(key)
    if not isinstance(value, bool):
        raise ValueError(f"{path} deve ser bool")
    return value
