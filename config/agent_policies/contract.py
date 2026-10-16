"""Contrato tipado e imutável de agent-policies (deny/ask dual-runtime)."""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path
from typing import Literal, Mapping, Pattern

from config.agent_policies.yaml_loader import load_mapping

Severity = Literal["deny", "ask"]

CORE_FAMILY_IDS: frozenset[str] = frozenset(
    {
        "shell",
        "docker",
        "git",
        "sql-cli",
        "databricks-cli",
        "terraform",
        "k8s",
    }
)


@dataclass(frozen=True, slots=True)
class PolicyPattern:
    """Pattern de comando com severity e artefato Claude deny."""

    id: str
    severity: Severity
    match: Pattern[str]
    tool_deny: str
    message: str


@dataclass(frozen=True, slots=True)
class PolicyFamily:
    """Família de patterns (core always-on ou extra opt-in)."""

    id: str
    description: str
    core: bool
    enabled_by_default: bool
    patterns: tuple[PolicyPattern, ...]


@dataclass(frozen=True, slots=True)
class AgentPoliciesContract:
    """Fonte normativa carregada de ``agent-policies.yaml``."""

    version: int
    core_families: tuple[str, ...]
    families: tuple[PolicyFamily, ...]

    @classmethod
    def load(cls, path: Path | str) -> AgentPoliciesContract:
        """Carrega e valida o contrato a partir de um path YAML."""
        return cls.from_mapping(load_mapping(Path(path)))

    @classmethod
    def from_mapping(cls, data: Mapping[str, object]) -> AgentPoliciesContract:
        """Valida um mapping no boundary e cria o contrato imutável."""
        version = _require_positive_int(data, "version", "version")
        core_families = _require_string_list(
            data, "core_families", "core_families"
        )
        families_mapping = _require_non_empty_mapping(data, "families", "families")

        families = tuple(
            _build_family(family_id, raw)
            for family_id, raw in families_mapping.items()
        )
        family_ids = {family.id for family in families}
        missing_core = [fid for fid in core_families if fid not in family_ids]
        if missing_core:
            raise ValueError(
                "core_families referencia famílias ausentes em families: "
                + ", ".join(missing_core)
            )

        for family in families:
            if family.core and family.id not in core_families:
                raise ValueError(
                    f"families.{family.id}.core=true mas id não está em core_families"
                )

        return cls(
            version=version,
            core_families=core_families,
            families=families,
        )

    def family(self, family_id: str) -> PolicyFamily:
        """Retorna uma família pelo ID."""
        for family in self.families:
            if family.id == family_id:
                return family
        raise KeyError(f"família desconhecida: {family_id}")

    def active_families(
        self,
        extra_family_ids: frozenset[str] | None = None,
    ) -> tuple[PolicyFamily, ...]:
        """Famílias ativas: core + enabled_by_default + extras do profile."""
        extras = extra_family_ids or frozenset()
        active: list[PolicyFamily] = []
        for family in self.families:
            if family.id in self.core_families or family.enabled_by_default:
                active.append(family)
                continue
            if family.id in extras:
                active.append(family)
        return tuple(active)


def _build_family(family_id: str, raw: object) -> PolicyFamily:
    path = f"families.{family_id}"
    mapping = _as_mapping(raw, path)
    patterns_mapping = _require_non_empty_mapping(
        mapping, "patterns", f"{path}.patterns"
    )
    patterns = tuple(
        _build_pattern(pattern_id, item, f"{path}.patterns.{pattern_id}")
        for pattern_id, item in patterns_mapping.items()
    )
    return PolicyFamily(
        id=_require_identifier(family_id, "family"),
        description=_require_string(mapping, "description", f"{path}.description"),
        core=_require_bool(mapping, "core", f"{path}.core"),
        enabled_by_default=_require_bool(
            mapping, "enabled_by_default", f"{path}.enabled_by_default"
        ),
        patterns=patterns,
    )


def _build_pattern(pattern_id: str, raw: object, path: str) -> PolicyPattern:
    mapping = _as_mapping(raw, path)
    severity_raw = _require_choice(
        mapping, "severity", f"{path}.severity", {"deny", "ask"}
    )
    severity: Severity = "deny" if severity_raw == "deny" else "ask"
    match_raw = _require_string(mapping, "match", f"{path}.match")
    try:
        compiled = re.compile(match_raw)
    except re.error as exc:
        raise ValueError(f"{path}.match regex inválida: {exc}") from exc
    return PolicyPattern(
        id=_require_identifier(pattern_id, "pattern"),
        severity=severity,
        match=compiled,
        tool_deny=_require_string(mapping, "tool_deny", f"{path}.tool_deny"),
        message=_require_string(mapping, "message", f"{path}.message"),
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


def _require_choice(
    data: Mapping[str, object],
    key: str,
    path: str,
    choices: set[str],
) -> str:
    value = _require_string(data, key, path)
    if value not in choices:
        options = ", ".join(sorted(choices))
        raise ValueError(f"{path} deve ser um de: {options}")
    return value


def _require_identifier(value: str, kind: str) -> str:
    if not value.strip():
        raise ValueError(f"ID de {kind} deve ser string não vazia")
    return value.strip()
