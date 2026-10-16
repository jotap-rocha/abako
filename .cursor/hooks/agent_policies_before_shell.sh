#!/usr/bin/env bash
# Cursor beforeShellExecution → guard compartilhado agent-policies
set -euo pipefail
exec python -m config.agent_policies.hooks.cursor_before_shell
