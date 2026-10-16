# Git Hygiene — cheatsheet (1 página)

Fonte de verdade: [`git-hygiene.yaml`](../../git-hygiene.yaml) · Comando: `/git-ajuda`

## Declaração §1.3 — limites reais dos gates

Nesta etapa, **nenhum gate impede de fato** uma ação errada sem `Edit policies` no Azure
DevOps (ou branch protection equivalente). Todos os gates locais são contornáveis
(`--no-verify`, clone sem bootstrap de hooks).

Objetivo: tornar o **caminho certo mais fácil** que o errado e tornar o errado **visível** —
sem falsa sensação de segurança. Critérios de aceite **não** afirmam bloqueio server-side.

## Branch

Formato: `{tipo}/{escopo-kebab}`

| Campo | Regra |
|---|---|
| `tipo` | `feat` \| `fix` \| `chore` |
| `escopo` | kebab-case ASCII, ≤ 40 chars, sem acento |
| Proibidos | `tmp`, `teste`, `nova-branch`, data solta (`2026-08-06` / `20260806`), nome de pessoa |

Exemplos válidos: `feat/gate-branch-isolada` · `fix/parser-data-nula` · `chore/atualiza-dependencias`

Criar branch: `/nova-branch` (fetch → sync `--ff-only` → acordo → `git switch -c`).

## Título de Pull Request (ponto de controle)

```
{tipo}({escopo}): {resumo ≤ 72 chars}
```

Exemplo: `feat(gate-branch-isolada): soft-block GIT_PREFLIGHT nos agents`

Merge preferido: **squash**. Prefixo `Merged PR NNN:` permanece aberto (não automatizado).

## Tronco e sync

- Tronco = default branch do remote (`origin/HEAD`); fallback `master`.
- Sync: `git pull --ff-only`. Divergência → soft-block humano (não force-push no tronco).
- Trabalhe sempre em branch isolada — nunca edite direto no tronco sem acordo explícito.

## Acordo explícito (obrigatório)

O agente **só** executa com “de acordo” do usuário:

| Ação | Sem acordo |
|---|---|
| `git commit` | Soft-block |
| `git push` | Soft-block |
| `git stash` | Soft-block |
| Descartar working tree (`reset --hard`, `clean -fd`, etc.) | Soft-block — nunca destrutivo sozinho |

## Hooks locais (`.githooks/`)

| Hook | MVP |
|---|---|
| `pre-commit` | Heurística leve de segredos — **bloqueante** |
| `commit-msg` | Aviso Conventional Commits — não bloqueia |
| `pre-push` | Aviso se push no tronco — **não bloqueia** neste MVP |

Bootstrap (idempotente, após confirmação):

```bash
git config core.hooksPath .githooks
```

## Segredos e PAT

- PAT / tokens: **somente** variável de ambiente ou secret manager.
- Nunca hardcoded, nunca em logs, nunca em URL query string.
- Diff com segredo óbvio → `pre-commit` bloqueia; rotacione se vazou.

## Adapter SCM

Detecção pelo remote: `dev.azure.com` / `visualstudio.com` → `azure`; `github.com` → `github`;
ambíguo → perguntar. Abrir PR: CLI (`az` / `gh`) se autenticada; senão payload para a UI.

## Soft-block `GIT_PREFLIGHT` (agents)

Antes de editar: fetch → tronco → sync → working tree → branch isolada. Se falhar, oferecer
`/nova-branch` e só seguir após acordo.
