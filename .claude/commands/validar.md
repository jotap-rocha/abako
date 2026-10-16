---
description: Gate rápido — ruff + mypy + pytest; data-check se marker DE, auto-detect SDP/DLT ou vault (secret_store / pacote E).
---

# /validar — gate rápido

Rode o gate de validação do time e **conserte até passar**. O hook de `Stop` cobre o
lado código (ruff/mypy/pytest); este comando é o gate explícito antes de commitar uma
fatia — e, quando o projeto for de dados, inclui o data-check.

## 1. Código (sempre)

```bash
SRC=$([ -d backend ] && echo backend || [ -d src ] && echo src || echo '')
if [ -n "$SRC" ]; then
  uv run ruff check --fix "$SRC" && uv run mypy "$SRC" && uv run pytest -q
else
  uv run ruff check --fix . && uv run mypy . && uv run pytest -q
fi
```

- Se **ruff** acusar: deixe o autofix resolver o que dá e corrija o resto à mão.
- Se **mypy** acusar: conserte a tipagem; não silencie com `# type: ignore` sem justificar.
- Se **pytest** falhar: conserte o código (não o teste, salvo se o teste estiver errado).

## 2. Engenharia de dados (condicional)

Fonte única (não reimplementar heurística em shell):
`config.canonical_data_check.de_marker.data_check_validate_argv` /
`should_run_data_check`.

Dispare o data-check quando o helper retornar argv — isto é:

- **marker** `.harness/data-check/project_profile.yaml` presente (Loop 1 / override), **ou**
- **auto-detect** Databricks com sinal útil de pipeline cloud (**SDP** e/ou **DLT**), **ou**
- **vault cloud**: campo `secret_store: oci|azure|multi` no marker **ou** auto-detect
  OCI Vault / Azure Key Vault (pacote **E** `keyvault-cloud`, regras `DE-E*`).

Não dispare quando:

- projeto comum (sem marker, sem SDP/DLT e sem vault) — gate só ruff + mypy + pytest;
- **DAB isolado** (`databricks.yml` / `bundle*.yml` sem SDP/DLT e sem vault) — detecta
  bundle, mas **não** escolhe perfil cloud nem ativa o data-check sem marker.

```bash
# Consultar o helper (fonte única) e, se houver argv, executar:
python - <<'PY'
from config.canonical_data_check.de_marker import data_check_validate_argv
import subprocess, sys
argv = data_check_validate_argv(".")
sys.exit(0 if argv is None else subprocess.call(argv))
PY

# Equivalente quando já sabe que o DE gate deve rodar:
python -m config.canonical_data_check validate .
```

Override via marker vence o auto-detect no **engine** (`resolve_effective_profile` /
`resolve_effective_secret_store`); o helper só decide se o validate entra no `/validar`.

IDs e severidade dos findings vêm de `data-engineering.yaml` (ver `rules/pipeline`) —
inclui perfis `databricks-*`, pacote D quando o perfil efetivo for cloud/multi, e
pacote E quando vault aplica (marker `secret_store` ou auto-detect).

Só considere a tarefa pronta quando o gate sair **verde**. Não comite vermelho.
