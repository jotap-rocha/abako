"""Contrato tipado e imutável da norma de Engenharia de Dados."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Mapping

from config.data_engineering.yaml_loader import load_mapping


class UnknownRuleError(KeyError):
    """Rule ID não existe na fonte normativa."""


@dataclass(frozen=True, slots=True)
class RuleDefinition:
    """Regra normativa com classificação e orientação para explain."""

    id: str
    category: str
    severity: str
    applicability: str
    title: str
    explanation: str
    remediation: str


@dataclass(frozen=True, slots=True)
class RulePackage:
    """Pacote de regras aplicável a uma classe de projetos."""

    id: str
    description: str
    applicability: str
    severity: str
    rules: tuple[RuleDefinition, ...]

    def rule(self, rule_id: str) -> RuleDefinition:
        """Retorna uma regra do pacote pelo ID."""
        for rule in self.rules:
            if rule.id == rule_id:
                return rule
        raise KeyError(f"regra desconhecida no pacote {self.id}: {rule_id}")


@dataclass(frozen=True, slots=True)
class ProjectProfile:
    """Perfil de projeto e os pacotes normativos habilitados."""

    id: str
    description: str
    package_ids: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class DataEngineeringContract:
    """Fonte normativa carregada de ``data-engineering.yaml``."""

    version: int
    profiles: tuple[ProjectProfile, ...]
    packages: tuple[RulePackage, ...]

    @classmethod
    def load(cls, path: Path | str) -> DataEngineeringContract:
        """Carrega e valida o contrato a partir de um path YAML."""
        return cls.from_mapping(load_mapping(Path(path)))

    @classmethod
    def from_mapping(
        cls,
        data: Mapping[str, object],
    ) -> DataEngineeringContract:
        """Valida um mapping no boundary e cria o contrato imutável."""
        version = _require_positive_int(data, "version", "version")
        profiles_mapping = _require_non_empty_mapping(data, "profiles", "profiles")
        packages_mapping = _require_non_empty_mapping(data, "packages", "packages")

        profiles = tuple(
            _build_profile(profile_id, raw_profile)
            for profile_id, raw_profile in profiles_mapping.items()
        )
        packages = tuple(
            _build_package(package_id, raw_package)
            for package_id, raw_package in packages_mapping.items()
        )

        known_package_ids = {package.id for package in packages}
        for profile in profiles:
            unknown = set(profile.package_ids) - known_package_ids
            if unknown:
                unknown_text = ", ".join(sorted(unknown))
                raise ValueError(
                    f"profiles.{profile.id}.packages referencia pacotes desconhecidos: "
                    f"{unknown_text}"
                )

        return cls(version=version, profiles=profiles, packages=packages)

    def profile(self, profile_id: str) -> ProjectProfile:
        """Retorna um perfil pelo ID."""
        for profile in self.profiles:
            if profile.id == profile_id:
                return profile
        raise KeyError(f"perfil desconhecido: {profile_id}")

    def package(self, package_id: str) -> RulePackage:
        """Retorna um pacote pelo ID."""
        for package in self.packages:
            if package.id == package_id:
                return package
        raise KeyError(f"pacote desconhecido: {package_id}")

    def rule(self, rule_id: str) -> RuleDefinition:
        """Retorna uma regra pelo ID em qualquer pacote."""
        for package in self.packages:
            for rule in package.rules:
                if rule.id == rule_id:
                    return rule
        raise UnknownRuleError(rule_id)


def _build_profile(profile_id: str, raw: object) -> ProjectProfile:
    path = f"profiles.{profile_id}"
    mapping = _as_mapping(raw, path)
    package_ids = _require_string_list(mapping, "packages", f"{path}.packages")
    return ProjectProfile(
        id=_require_identifier(profile_id, "profile"),
        description=_require_string(mapping, "description", f"{path}.description"),
        package_ids=package_ids,
    )


def _build_package(package_id: str, raw: object) -> RulePackage:
    path = f"packages.{package_id}"
    mapping = _as_mapping(raw, path)
    rules_mapping = _require_non_empty_mapping(mapping, "rules", f"{path}.rules")
    rules = tuple(
        _build_rule(rule_id, raw_rule, path)
        for rule_id, raw_rule in rules_mapping.items()
    )
    return RulePackage(
        id=_require_identifier(package_id, "package"),
        description=_require_string(mapping, "description", f"{path}.description"),
        applicability=_require_choice(
            mapping,
            "applicability",
            f"{path}.applicability",
            {"universal", "profile", "conditional"},
        ),
        severity=_require_choice(
            mapping,
            "severity",
            f"{path}.severity",
            {"blocker", "warning"},
        ),
        rules=rules,
    )


def _build_rule(rule_id: str, raw: object, package_path: str) -> RuleDefinition:
    path = f"{package_path}.rules.{rule_id}"
    mapping = _as_mapping(raw, path)
    return RuleDefinition(
        id=_require_identifier(rule_id, "rule"),
        category=_require_string(mapping, "category", f"{path}.category"),
        severity=_require_choice(
            mapping,
            "severity",
            f"{path}.severity",
            {"blocker", "warning"},
        ),
        applicability=_require_string(
            mapping,
            "applicability",
            f"{path}.applicability",
        ),
        title=_require_string(mapping, "title", f"{path}.title"),
        explanation=_require_string(mapping, "explanation", f"{path}.explanation"),
        remediation=_require_string(mapping, "remediation", f"{path}.remediation"),
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


def _require_string(
    data: Mapping[str, object],
    key: str,
    path: str,
) -> str:
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


def _require_positive_int(
    data: Mapping[str, object],
    key: str,
    path: str,
) -> int:
    value = data.get(key)
    if not isinstance(value, int) or isinstance(value, bool) or value < 1:
        raise ValueError(f"{path} deve ser inteiro positivo")
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
