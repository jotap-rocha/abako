#!/usr/bin/env bash
# Claude PreToolUse → guard compartilhado agent-policies
set -euo pipefail
exec python -m config.agent_policies.hooks.claude_pretooluse
