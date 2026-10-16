"""Generate dual artifacts: Claude permissions.deny + Cursor hooks.json."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

from config.agent_policies.contract import AgentPoliciesContract
from config.agent_policies.yaml_loader import load_mapping

HOOKS_JSON_NAME = "hooks.json"
CLAUDE_DENY_FRAGMENT = "claude_permissions_deny.json"
CURSOR_HOOKS_FRAGMENT = "cursor_hooks.json"


@dataclass(frozen=True, slots=True)
class GenerateResult:
    """Artefatos gerados a partir do mesmo catálogo ativo."""

    claude_deny: tuple[str, ...]
    cursor_hooks: dict[str, object]
    active_family_ids: tuple[str, ...]

    def to_summary(self) -> str:
        payload = {
            "active_families": list(self.active_family_ids),
            "claude_deny_count": len(self.claude_deny),
            "claude_deny": list(self.claude_deny),
            "cursor_hooks": self.cursor_hooks,
        }
        return json.dumps(payload, indent=2, ensure_ascii=False) + "\n"


def load_profile_families(profile_path: Path | None) -> frozenset[str]:
    """Lê ``families[]`` extras do project_profile (opt-in)."""
    if profile_path is None or not profile_path.is_file():
        return frozenset()
    data = load_mapping(profile_path)
    raw = data.get("families")
    if raw is None:
        return frozenset()
    # MinimalYamlLoader: `families:` sem filhos → {}; `families: []` → string "[]"
    if isinstance(raw, dict) and not raw:
        return frozenset()
    if isinstance(raw, str) and raw.strip() in {"", "[]"}:
        return frozenset()
    if not isinstance(raw, list):
        raise ValueError(
            "project_profile.families deve ser lista (use block-style; "
            "não use families: [])"
        )
    return frozenset(str(item).strip() for item in raw if str(item).strip())


def generate_artifacts(
    *,
    contract_path: Path | str,
    profile_path: Path | str | None = None,
) -> GenerateResult:
    """Materializa deny Claude + hooks Cursor sem drift."""
    contract = AgentPoliciesContract.load(contract_path)
    extras = load_profile_families(
        Path(profile_path) if profile_path else None
    )
    active = contract.active_families(extras)
    deny_entries: list[str] = []
    seen: set[str] = set()
    for family in active:
        for pattern in family.patterns:
            if pattern.severity != "deny":
                continue
            if pattern.tool_deny in seen:
                continue
            seen.add(pattern.tool_deny)
            deny_entries.append(pattern.tool_deny)

    if not deny_entries:
        raise ValueError("generate produziu permissions.deny vazio — catálogo core inválido")

    cursor_hooks = {
        "version": 1,
        "hooks": {
            "beforeShellExecution": [
                {
                    "command": ".cursor/hooks/agent_policies_before_shell.sh",
                    "description": "agent-policies guard (deny/ask/allow)",
                }
            ]
        },
        "active_families": [family.id for family in active],
        "policy_source": "agent-policies.yaml",
    }
    return GenerateResult(
        claude_deny=tuple(deny_entries),
        cursor_hooks=cursor_hooks,
        active_family_ids=tuple(family.id for family in active),
    )


def write_artifacts(result: GenerateResult, out_dir: Path) -> None:
    """Escreve fragmentos JSON sob ``out_dir`` (portátil, sem path de máquina)."""
    out_dir.mkdir(parents=True, exist_ok=True)
    deny_path = out_dir / CLAUDE_DENY_FRAGMENT
    deny_path.write_text(
        json.dumps(list(result.claude_deny), indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    hooks_path = out_dir / CURSOR_HOOKS_FRAGMENT
    hooks_path.write_text(
        json.dumps(result.cursor_hooks, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    # hooks.json canônico Cursor (mesmo conteúdo do fragmento)
    (out_dir / HOOKS_JSON_NAME).write_text(
        json.dumps(result.cursor_hooks, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )


def build_claude_pretooluse_hooks() -> dict[str, object]:
    """Fragmento PreToolUse Claude apontando ao adapter compartilhado."""
    return {
        "PreToolUse": [
            {
                "matcher": "Bash",
                "hooks": [
                    {
                        "type": "command",
                        "command": ".claude/hooks/agent_policies_pretooluse.sh",
                    }
                ],
            }
        ]
    }
