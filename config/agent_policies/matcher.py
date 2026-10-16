"""Matcher determinístico: comando shell → deny | ask | allow."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

from config.agent_policies.contract import (
    AgentPoliciesContract,
    PolicyFamily,
    PolicyPattern,
)

Action = Literal["deny", "ask", "allow"]


@dataclass(frozen=True, slots=True)
class PolicyDecision:
    """Decisão auditável do matcher compartilhado."""

    action: Action
    family_id: str | None
    pattern_id: str | None
    message: str
    severity: str | None = None


def match_command(
    command: str,
    contract: AgentPoliciesContract,
    *,
    extra_family_ids: frozenset[str] | None = None,
) -> PolicyDecision:
    """Avalia ``command`` contra famílias ativas.

    Deny vence ask quando ambos casam (mais restritivo).
    Fora do catálogo → allow.
    """
    families = contract.active_families(extra_family_ids)
    deny_hit = _first_match(command, families, severity="deny")
    if deny_hit is not None:
        family, pattern = deny_hit
        return PolicyDecision(
            action="deny",
            family_id=family.id,
            pattern_id=pattern.id,
            message=f"[{family.id}/{pattern.id}] {pattern.message}",
            severity="deny",
        )
    ask_hit = _first_match(command, families, severity="ask")
    if ask_hit is not None:
        family, pattern = ask_hit
        return PolicyDecision(
            action="ask",
            family_id=family.id,
            pattern_id=pattern.id,
            message=f"[{family.id}/{pattern.id}] {pattern.message}",
            severity="ask",
        )
    return PolicyDecision(
        action="allow",
        family_id=None,
        pattern_id=None,
        message="allow",
        severity=None,
    )


def _first_match(
    command: str,
    families: tuple[PolicyFamily, ...],
    *,
    severity: str,
) -> tuple[PolicyFamily, PolicyPattern] | None:
    for family in families:
        for pattern in family.patterns:
            if pattern.severity != severity:
                continue
            if pattern.match.search(command) is not None:
                return family, pattern
    return None
