#!/usr/bin/env bash
# bootstrap-githooks.sh — configura core.hooksPath=.githooks de forma idempotente.
# Uso: ./scripts/bootstrap-githooks.sh [raiz-do-repo]
set -euo pipefail

ROOT="${1:-$(cd "$(dirname "$0")/.." && pwd)}"
cd "$ROOT"

if [[ ! -d .githooks ]]; then
  echo "[git-hygiene] ERRO: pasta .githooks não encontrada em $ROOT" >&2
  exit 1
fi

if [[ ! -d .git ]]; then
  echo "[git-hygiene] ERRO: $ROOT não é um repositório git" >&2
  exit 1
fi

# Garantir executáveis
chmod +x .githooks/pre-commit .githooks/commit-msg .githooks/pre-push 2>/dev/null || true

current=$(git config --get core.hooksPath || true)
if [[ "$current" == ".githooks" ]]; then
  echo "[git-hygiene] core.hooksPath já é .githooks (idempotente — nada a fazer)."
  exit 0
fi

git config core.hooksPath .githooks
echo "[git-hygiene] core.hooksPath=.githooks configurado em $ROOT"
git config --get core.hooksPath
