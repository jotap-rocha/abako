"""Apresentação sanitizada de findings e explicações normativas."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from config.canonical_data_check.findings import Finding, ValidationResult
from config.data_engineering import DataEngineeringContract, RuleDefinition


@dataclass(frozen=True, slots=True)
class ReportFinding:
    """Visão mínima de um finding, sem conteúdo potencialmente sensível."""

    rule_id: str
    severity: str
    status: str
    path: str

    @classmethod
    def from_finding(cls, finding: Finding) -> ReportFinding:
        return cls(
            rule_id=finding.rule_id,
            severity=finding.severity,
            status=finding.status,
            path=finding.path,
        )

    def to_dict(self) -> dict[str, str]:
        return {
            "rule_id": self.rule_id,
            "severity": self.severity,
            "status": self.status,
            "path": self.path,
        }


@dataclass(frozen=True, slots=True)
class ComplianceReport:
    """Relatório determinístico derivado do resultado do engine."""

    exit_code: int
    profile: str
    findings: tuple[ReportFinding, ...]

    @classmethod
    def from_validation(cls, result: ValidationResult) -> ComplianceReport:
        return cls(
            exit_code=result.exit_code,
            profile=result.profile,
            findings=tuple(
                ReportFinding.from_finding(finding) for finding in result.findings
            ),
        )

    def to_dict(self) -> dict[str, object]:
        return {
            "exit_code": self.exit_code,
            "profile": self.profile,
            "findings": [finding.to_dict() for finding in self.findings],
        }

    def to_markdown(self) -> str:
        lines = [
            "# Relatório de conformidade DE",
            "",
            f"- Perfil: `{_escape_inline(self.profile)}`",
            f"- Exit code: `{self.exit_code}`",
            f"- Findings: `{len(self.findings)}`",
            "",
            "| Rule ID | Severidade | Status | Path |",
            "|---|---|---|---|",
        ]
        lines.extend(
            "| "
            f"{_escape_cell(item.rule_id)} | "
            f"{_escape_cell(item.severity)} | "
            f"{_escape_cell(item.status)} | "
            f"{_escape_cell(item.path)} |"
            for item in self.findings
        )
        if not self.findings:
            lines.append("| — | — | pass | — |")
        return "\n".join(lines) + "\n"


@dataclass(frozen=True, slots=True)
class RuleExplanation:
    """Texto acionável de uma regra carregada do contrato YAML."""

    rule_id: str
    title: str
    applicability: str
    explanation: str
    remediation: str

    @classmethod
    def from_rule(cls, rule: RuleDefinition) -> RuleExplanation:
        return cls(
            rule_id=rule.id,
            title=rule.title,
            applicability=rule.applicability,
            explanation=rule.explanation,
            remediation=rule.remediation,
        )

    def to_text(self) -> str:
        return (
            f"{self.rule_id} — {self.title}\n"
            f"Aplicabilidade: {self.applicability}\n"
            f"Descrição: {self.explanation}\n"
            f"Remediação: {self.remediation}\n"
        )


def explain_rule(rule_id: str, contract_path: Path | str) -> RuleExplanation:
    """Carrega uma regra diretamente da fonte normativa YAML."""
    contract = DataEngineeringContract.load(contract_path)
    return RuleExplanation.from_rule(contract.rule(rule_id))


def _escape_cell(value: str) -> str:
    return _escape_inline(value).replace("|", r"\|")


def _escape_inline(value: str) -> str:
    return value.replace("\r", " ").replace("\n", " ")
