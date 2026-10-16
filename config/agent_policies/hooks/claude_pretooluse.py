"""Adapter Claude PreToolUse — stdin JSON → exit 0 allow/ask, exit 2 deny."""

from __future__ import annotations

import json
import sys
from typing import Any

from config.agent_policies.guard import evaluate_command


def extract_command(payload: dict[str, Any]) -> str:
    """Extrai comando Bash do payload PreToolUse (várias formas conhecidas)."""
    tool_input = payload.get("tool_input") or payload.get("input") or {}
    if isinstance(tool_input, dict):
        for key in ("command", "cmd", "bash"):
            value = tool_input.get(key)
            if isinstance(value, str) and value.strip():
                return value
    direct = payload.get("command")
    if isinstance(direct, str) and direct.strip():
        return direct
    return ""


def handle_payload(payload: dict[str, Any]) -> tuple[int, dict[str, Any]]:
    """Retorna (exit_code, response_json).

    Claude: exit 2 = block; exit 0 = proceed (ask tratado pelo runtime via mensagem).
    """
    command = extract_command(payload)
    if not command:
        return 0, {"permission": "allow", "message": "empty command"}

    result = evaluate_command(command, adapter="claude-pretooluse")
    body = {
        "permission": result.action,
        "family": result.family_id,
        "pattern": result.pattern_id,
        "message": result.message,
        "bypassed": result.bypassed,
    }
    if result.action == "deny":
        return 2, body
    # ask e allow → exit 0; ask inclui permission=ask no JSON para o runtime
    return 0, body


def main(argv: list[str] | None = None) -> int:
    del argv  # stdin-driven
    raw = sys.stdin.read()
    try:
        payload = json.loads(raw) if raw.strip() else {}
    except json.JSONDecodeError as exc:
        # Fail closed: payload ilegível em PreToolUse Bash
        print(json.dumps({"permission": "deny", "message": f"invalid json: {exc}"}))
        return 2
    if not isinstance(payload, dict):
        print(json.dumps({"permission": "deny", "message": "payload must be object"}))
        return 2
    code, body = handle_payload(payload)
    print(json.dumps(body, ensure_ascii=False))
    return code


if __name__ == "__main__":
    raise SystemExit(main())
