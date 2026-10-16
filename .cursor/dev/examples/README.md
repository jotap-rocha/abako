# Exemplos reais de Dev Loop

Esta pasta acumula exemplos reais (`PROMPT_*.md` + `PROGRESS_*.md` + `LOG_*.md`) conforme o
Dev Loop for usado neste repositório — ainda vazia.

## Por que vazia

O projeto de origem do Dev Loop (`bootcamp-zero-to-claude-code-prd`) trazia um exemplo real
completo (extração de invoice via LLM, ~27 iterações, ~7000 LOC) — decidimos não trazer esse
exemplo pra cá porque é grande e específico de outro domínio (GCP/Gemini/Parquet), sem relação
com o que este harness cobre. Os templates em `../templates/` (`PROMPT_EXAMPLE_FEATURE.md`,
`PROMPT_EXAMPLE_KB.md`) já demonstram a mecânica adequadamente.

## O que vai aqui

Quando você rodar um `/dev tasks/PROMPT_X.md` até `EXIT_COMPLETE` e achar que virou um bom
exemplo de referência (padrão de task bem quebrado, uso de `@agente`, recovery via `--resume`),
copie o trio `PROMPT_X.md` + `PROGRESS_X.md` + `LOG_X_*.md` pra cá.

## Ver também

- `../templates/PROMPT_EXAMPLE_FEATURE.md` — exemplo mínimo: utilitário Python
- `../templates/PROMPT_EXAMPLE_KB.md` — exemplo mínimo: domínio de KB
- `DEV-LOOP.md` (raiz) — conceito completo
