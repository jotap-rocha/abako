---
description: >-
  Dev Loop — execução ágil de tarefa pontual (1-4h) com PROMPT.md, verificação por exit
  code e recovery de sessão. Ver DEV-LOOP.md na raiz do repo. Use quando: "/dev cria X",
  "/dev tasks/PROMPT_X.md", "/dev tasks/PROMPT_X.md --resume".
---

# /dev — Dev Loop

## Git (GIT_PREFLIGHT)

Antes de craft ou execute: soft-block `GIT_PREFLIGHT` (fetch → tronco → sync →
working tree → branch isolada). Ofereça `/nova-branch` se estiver no tronco.
Commit/push/stash/descartar só com acordo explícito. Ver rule `git-hygiene`.


Roteia entre os dois agentes do Dev Loop conforme o argumento.

## Uso

```bash
# Craft — descrição vira PROMPT via entrevista
/dev "quero criar um parser de data"

# Execute — roda um PROMPT já existente
/dev tasks/PROMPT_DATE_PARSER.md
/dev tasks/PROMPT_DATE_PARSER.md --mode afk

# Retomar sessão interrompida
/dev tasks/PROMPT_DATE_PARSER.md --resume

# Validar sem executar
/dev tasks/PROMPT_DATE_PARSER.md --dry-run

# Listar PROMPTs disponíveis
/dev --list
```

## Roteamento

| Argumento | Ação |
|---|---|
| `"descrição"` (texto livre) | Aciona `prompt-crafter` — pergunta antes de gerar o PROMPT |
| `tasks/PROMPT_*.md` (path) | Aciona `dev-loop-executor` — executa o PROMPT |
| `--list` | Lista os PROMPTs em `.claude/dev/tasks/` |

## Opções (quando executando um PROMPT)

| Opção | Descrição |
|---|---|
| `--mode hitl` | Human-in-the-loop (padrão) — pausa para revisão |
| `--mode afk` | Autônomo — roda sem pausar |
| `--resume` | Retoma do arquivo PROGRESS existente |
| `--dry-run` | Valida e mostra o plano sem executar |
| `--max N` | Sobrescreve o número máximo de iterações (padrão: 30) |

## Quando usar `/dev` em vez de `/novo-projeto`

`/dev` é para tarefa pontual de 1-4h (utilitário, KB, refactor pequeno) sem o overhead do
fluxo completo de projeto. Para escopo de projeto inteiro, com PRD/harness/tasks e gate
obrigatório, use `/novo-projeto`. Ver a tabela comparativa em `DEV-LOOP.md` (raiz).

## Gate Medallion (tarefas de pipeline)

Quando a descrição mencionar pipeline, medallion, bronze, silver, gold ou ingestão, o
`prompt-crafter` aciona o checklist de `kb/pipeline/patterns/medallion-sdd-gates.md`
(tabelas, colunas/amostra, `_source_system`). Escopo multi-camada ou greenfield → use
`/novo-projeto` em vez de `/dev`.

## Referências

- `DEV-LOOP.md` (raiz) — conceito completo, introdução e como usar
- `.claude/dev/_index.md` — documentação técnica detalhada
- `.claude/agents/dev/prompt-crafter.md` — agente de crafting
- `.claude/agents/dev/dev-loop-executor.md` — agente de execução
- `docs/cheatsheets/fluxo-events-cheatsheet.md` — telemetria live Dev Loop (`dev-loop-*`)
- `/fluxo-live` — abrir/servir `live.html`

## Telemetria live (fluxo-events)

No craft/execute, avise 1× o path do painel:
`.claude/projetos/dev-loop-{nome}/fluxo/live.html` (http.server opcional; atalho `/fluxo-live`).
Emit fail-soft sob slug `dev-loop-*`. Causalidade: use `--run-id` / `--parent-event-id` quando souber o parent; senão o stack
`projetos/dev-loop-{nome}/fluxo/stack.json` (gitignore; fail-soft). **`--dry-run` não emite**.
