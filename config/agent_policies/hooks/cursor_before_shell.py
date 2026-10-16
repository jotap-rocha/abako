"""Adapter Cursor beforeShellExecution — stdin JSON → permission deny|ask|allow."""

from __future__ import annotations

import json
import sys
from typing import Any

from config.agent_policies.guard import evaluate_command


def extract_command(payload: dict[str, Any]) -> str:
    """Extrai comando do payload Cursor beforeShellExecution."""
    for key in ("command", "shellCommand", "cmd"):
        value = payload.get(key)
        if isinstance(value, str) and value.strip():
            return value
    nested = payload.get("input")
    if isinstance(nested, dict):
        value = nested.get("command")
        if isinstance(value, str) and value.strip():
            return value
    return ""


def handle_payload(payload: dict[str, Any]) -> dict[str, Any]:
    command = extract_command(payload)
    if not command:
        return {"permission": "allow", "message": "empty command"}

    result = evaluate_command(command, adapter="cursor-before-shell")
    return {
        "permission": result.action,
        "family": result.family_id,
        "pattern": result.pattern_id,
        "message": result.message,
        "bypassed": result.bypassed,
    }


def main(argv: list[str] | None = None) -> int:
    del argv
    raw = sys.stdin.read()
    try:
        payload = json.loads(raw) if raw.strip() else {}
    except json.JSONDecodeError as exc:
        # Fail closed no path de shell destrutivo potencial
        print(
            json.dumps(
                {"permission": "deny", "message": f"invalid json: {exc}"},
                ensure_ascii=False,
            )
        )
        return 0
    if not isinstance(payload, dict):
        print(json.dumps({"permission": "deny", "message": "payload must be object"}))
        return 0
    body = handle_payload(payload)
    print(json.dumps(body, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
