"""Modelo imutável de finding e resultado de validação."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable


@dataclass(frozen=True, slots=True)
class Finding:
    """Achado determinístico emitido por um check."""

    rule_id: str
    severity: str
    status: str
    path: str
    message: str

    def to_dict(self) -> dict[str, str]:
        return {
            "rule_id": self.rule_id,
            "severity": self.severity,
            "status": self.status,
            "path": self.path,
            "message": self.message,
        }


@dataclass(frozen=True, slots=True)
class ValidationResult:
    """Resultado agregado de ``validate``."""

    exit_code: int
    findings: tuple[Finding, ...]
    profile: str

    def to_dict(self) -> dict[str, object]:
        return {
            "exit_code": self.exit_code,
            "profile": self.profile,
            "findings": [finding.to_dict() for finding in self.findings],
        }


def sort_findings(findings: Iterable[Finding]) -> tuple[Finding, ...]:
    """Ordena findings para saída determinística."""
    return tuple(
        sorted(
            findings,
            key=lambda item: (item.rule_id, item.status, item.path, item.message),
        )
    )
