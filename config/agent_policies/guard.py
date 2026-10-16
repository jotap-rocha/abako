"""Guard sobre o matcher: bypass env + fail closed/open."""

from __future__ import annotations

import os
import sys
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Literal

from config.agent_policies.contract import AgentPoliciesContract
from config.agent_policies.matcher import PolicyDecision, match_command

BYPASS_ENV = "HARNESS_ALLOW_DESTRUCTIVE"
Action = Literal["deny", "ask", "allow"]
FailMode = Literal["closed", "open", "none"]


def resolve_profile_path(explicit: Path | str | None = None) -> Path | None:
    """Resolve profile do filho: argumento → cwd/.harness/policies → None."""
    if explicit is not None:
        path = Path(explicit)
        return path if path.is_file() else None
    candidate = Path.cwd() / ".harness" / "policies" / "project_profile.yaml"
    return candidate if candidate.is_file() else None


@dataclass(frozen=True, slots=True)
class GuardResult:
    """Resultado do guard (adapters Claude/Cursor consomem isto)."""

    action: Action
    family_id: str | None
    pattern_id: str | None
    message: str
    bypassed: bool = False
    fail_mode: FailMode = "none"
    error: str | None = None
    warning: str | None = None


def evaluate_command(
    command: str,
    *,
    contract_path: Path | str | None = None,
    profile_path: Path | str | None = None,
    extra_family_ids: frozenset[str] | None = None,
    assumed_severity: Literal["deny", "ask"] | None = None,
    adapter: str = "shared",
) -> GuardResult:
    """Avalia comando com bypass e fail modes.

    ``assumed_severity`` só entra quando o contrato/engine falha:
    deny → fail closed; ask → fail open.
    Se omitido e o engine quebra, assume fail closed (SI d).

    Extras opt-in: ``extra_family_ids`` ou ``.harness/policies/project_profile.yaml``.
    """
    path = Path(contract_path) if contract_path else _default_contract_path()

    try:
        from config.agent_policies.generate import load_profile_families

        extras = extra_family_ids
        if extras is None:
            extras = load_profile_families(resolve_profile_path(profile_path))
        contract = AgentPoliciesContract.load(path)
        decision = match_command(
            command, contract, extra_family_ids=extras
        )
    except Exception as exc:  # noqa: BLE001 — boundary do guard
        return _fail_mode_result(exc, assumed_severity)

    if decision.action == "deny" and _bypass_enabled():
        _log_bypass(decision, adapter=adapter, command=command)
        return GuardResult(
            action="allow",
            family_id=decision.family_id,
            pattern_id=decision.pattern_id,
            message=f"bypass:{decision.message}",
            bypassed=True,
        )

    return GuardResult(
        action=decision.action,
        family_id=decision.family_id,
        pattern_id=decision.pattern_id,
        message=decision.message,
        bypassed=False,
    )


def _fail_mode_result(
    exc: Exception,
    assumed_severity: Literal["deny", "ask"] | None,
) -> GuardResult:
    severity = assumed_severity or "deny"
    err = f"{type(exc).__name__}: {exc}"
    if severity == "ask":
        warning = f"agent-policies fail-open (ask): {err}"
        print(f"WARN {warning}", file=sys.stderr)
        return GuardResult(
            action="allow",
            family_id=None,
            pattern_id=None,
            message=warning,
            fail_mode="open",
            error=err,
            warning=warning,
        )
    message = f"agent-policies fail-closed (deny): {err}"
    print(f"ERROR {message}", file=sys.stderr)
    return GuardResult(
        action="deny",
        family_id=None,
        pattern_id=None,
        message=message,
        fail_mode="closed",
        error=err,
    )


def _bypass_enabled() -> bool:
    return os.environ.get(BYPASS_ENV, "").strip() == "1"


def _log_bypass(
    decision: PolicyDecision,
    *,
    adapter: str,
    command: str,
) -> None:
    # Redação leve: nunca logar valor de secret; truncar comando longo.
    safe_cmd = _redact_command(command)
    ts = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    print(
        f"AUDIT bypass ts={ts} adapter={adapter} "
        f"family={decision.family_id} pattern={decision.pattern_id} "
        f"decision=bypass cmd={safe_cmd!r}",
        file=sys.stderr,
    )


def _redact_command(command: str, max_len: int = 120) -> str:
    lowered = command.lower()
    for needle in ("password", "token", "secret", "api_key", "apikey"):
        if needle in lowered:
            return "<redacted-credential-like>"
    if len(command) > max_len:
        return command[:max_len] + "…"
    return command


def _default_contract_path() -> Path:
    return Path(__file__).resolve().parents[2] / "agent-policies.yaml"
