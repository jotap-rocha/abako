---
name: sync-context
description: >-
  Detecta drift entre os arquivos de contexto vivos (CLAUDE.md, AGENTS.md, HANDOFF.md,
  CONTEXT.md, docs/adr/) e o estado real do código — e atualiza o que ficou desatualizado.
  Nunca inventa: só sincroniza o que já está implementado. Use quando: "o CLAUDE.md está
  desatualizado", "atualiza o contexto do projeto", "sincroniza o handoff", "o que mudou desde
  a última sessão?", "o CONTEXT.md não reflete mais o código".
---

# Sync Context

Detecta e corrige drift entre documentação de contexto e código real.
**Regra central:** nunca adicionar o que não está implementado. Só descrever o que existe.

## Arquivos de contexto gerenciados

| Arquivo | Propósito | Quando atualizar |
|---|---|---|
| `CLAUDE.md` | Invariantes, stack, comandos — carrega em toda sessão | Stack mudou, novo invariante, novo comando |
| `AGENTS.md` | Espelho portátil do CLAUDE.md (Cursor/Windsurf/Codex) | Sempre que CLAUDE.md mudar |
| `HANDOFF.md` | Estado da sessão atual — ponto de continuidade | Fim de sessão ou mudança de escopo |
| `CONTEXT.md` | Domínio e decisões — single-context do projeto | Nova decisão, novo fluxo implementado |
| `docs/adr/` | Decisões arquiteturais registradas | Nova ADR criada ou decisão revertida |

## Scripts

Ambos usam só stdlib — rodam em qualquer projeto que tenha a skill instalada.

| Script | Responsabilidade | Escreve? |
|---|---|---|
| `scripts/check_context_drift.py` | Compara stack/serviços/env declarados vs. reais | Não |
| `scripts/sync_agents_from_claude.py` | Deriva `AGENTS.md` do `CLAUDE.md` | Só com `--apply` |

```bash
python3 .claude/skills/sync-context/scripts/check_context_drift.py --warn   # imprime, exit 0
python3 .claude/skills/sync-context/scripts/check_context_drift.py --check  # exit 1 se drift
python3 .claude/skills/sync-context/scripts/check_context_drift.py --json   # saída estruturada

python3 .claude/skills/sync-context/scripts/sync_agents_from_claude.py --check  # exit 1 se divergiu
python3 .claude/skills/sync-context/scripts/sync_agents_from_claude.py --diff   # preview
python3 .claude/skills/sync-context/scripts/sync_agents_from_claude.py --apply  # grava
```

## Processo

### Passo 1 — Inventário do que existe no código

Use o detector automatizado:

```bash
python3 .claude/skills/sync-context/scripts/check_context_drift.py --json
```

Ele coleta dependências (`requirements.txt`, `pyproject.toml`, `package.json`), serviços
(`docker-compose.yml`), nomes de variáveis de ambiente (`.env.example` — nunca `.env`) e
commits desde a última alteração do `CLAUDE.md`, e aponta o que não está declarado.

Se o script não estiver disponível, faça o inventário à mão:

```bash
# Entry points, routers, serviços ativos
find . -name "*.py" -o -name "*.ts" -o -name "*.go" | grep -v test | head -40

# Docker services rodando
grep -A3 "services:" docker-compose.yml 2>/dev/null || true

# Variáveis de ambiente reais
cat .env.example 2>/dev/null || true
```

### Passo 2 — Leitura dos arquivos de contexto atuais

Leia cada arquivo listado na tabela acima e anote:
- O que está declarado
- O que parece desatualizado (serviço removido, rota inexistente, variável obsoleta)
- O que está implementado mas não documentado

### Passo 3 — Gerar relatório de drift

Antes de editar qualquer coisa, exibir o relatório:

```markdown
## Relatório de Drift — {data}

### Desatualizado (presente no contexto, ausente no código)
- [ ] {descrição exata do que está errado e em qual arquivo}

### Ausente (presente no código, não documentado no contexto)
- [ ] {o que falta documentar}

### Correto (sem mudança necessária)
- {lista do que está em sync}
```

Aguardar confirmação do usuário antes de aplicar as mudanças.

### Passo 4 — Aplicar atualizações

Para cada item "desatualizado" ou "ausente" confirmado:
1. Editar apenas a seção específica do arquivo — não reescrever tudo
2. Manter o estilo e tom do documento existente
3. Citar evidência do código (`arquivo:linha`) para cada adição

Se o `CLAUDE.md` mudou, **não edite o `AGENTS.md` à mão** — ele é derivado:

```bash
python3 .claude/skills/sync-context/scripts/sync_agents_from_claude.py --diff   # revisar
python3 .claude/skills/sync-context/scripts/sync_agents_from_claude.py --apply  # aplicar
```

Conteúdo que só faz sentido no `AGENTS.md` (ex.: seção "Como usar no Cursor") fica protegido
entre `<!-- agents-only:start -->` e `<!-- agents-only:end -->` — o script preserva esses blocos.

### Passo 5 — Confirmar sync

Exibir diff resumido do que foi alterado:
```
CLAUDE.md: seção "Stack" — adicionado Redis, removido RabbitMQ
AGENTS.md: espelho regenerado a partir do CLAUDE.md
HANDOFF.md: estado atual atualizado para refletir PR #42 mergeado
CONTEXT.md: novo fluxo de autenticação documentado
```

## Quando o sync é obrigatório

Critério 7 da DoD (`rules/definicao-de-pronto.md`) — um fluxo não fecha com contexto
desatualizado:

| Fluxo | Gatilho |
|---|---|
| `/novo-projeto` (SDD) | Passo 2 do `harness-ship` |
| `/dev` (Dev Loop) | Step 11 (SYNC) do `dev-loop-executor`, em `EXIT_COMPLETE` |
| Qualquer sessão | Hook `Stop` roda `check_context_drift.py --warn` (avisa, não bloqueia) |

## O que NÃO fazer

- Não adicionar funcionalidades "planejadas" que não estão no código
- Não reescrever o estilo ou reestruturar documentos desnecessariamente
- Não atualizar ADRs — ADRs são imutáveis (nova decisão = nova ADR)
- Não editar sem mostrar o relatório de drift primeiro
- Não editar `AGENTS.md` à mão — use o script de derivação
- Não ler `.env` (só `.env.example`) — valores de secret nunca entram no relatório

## Referências

- `CLAUDE.md` — template de invariantes de projeto
- `HANDOFF.md` — template de estado de sessão
- `.claude/rules/definicao-de-pronto.md` — critério 7 (contexto sincronizado)
- `.claude/agents/dev/codebase-explorer.md` — para mapear o código antes do sync
