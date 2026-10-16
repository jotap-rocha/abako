# Dev Loop — documentação técnica completa

> Ver `DEV-LOOP.md` na raiz do repo para a introdução. Este arquivo é a referência técnica —
> lido pelos agentes `prompt-crafter`/`dev-loop-executor`, não pelo usuário toda vez.

## Como funciona

```text
/dev "descrição"                           /dev tasks/PROMPT_*.md
      │                                           │
      ▼                                           ▼
┌─────────────────┐                       ┌─────────────────┐
│  PROMPT CRAFTER  │                       │  DEV LOOP        │
│                  │                       │  EXECUTOR        │
│  1. Explora      │                       │                  │
│  2. Pergunta     │ ──── gera ──────────→ │  1. Load         │
│  3. Desenha      │      PROMPT.md        │  2. Pick (🔴→🟡→🟢) │
│  4. Confirma     │                       │  3. Execute      │
└─────────────────┘                       │  4. Verify       │
                                           │  5. Update       │
                                           │  6. Loop         │
                                           │  7. Sync context │
                                           └────────┬─────────┘
                                                    │
                                                    ▼
                                           ┌─────────────────┐
                                           │  EXIT_COMPLETE  │
                                           └─────────────────┘
```

## Conceitos-chave

### Quality Tiers

| Tier | Comportamento |
|---|---|
| `prototype` | Velocidade acima de perfeição. Verificação mínima. |
| `production` | Testes obrigatórios. Verificação completa. |
| `library` | Compatibilidade retroativa. Documentação completa. |

### Prioridade de task

| Prioridade | Símbolo | Ordem de execução |
|---|---|---|
| RISKY | 🔴 | Primeiro — falha rápido em problema difícil |
| CORE | 🟡 | Segundo — implementação principal |
| POLISH | 🟢 | Último — limpeza e otimização |

### Modos de execução

| Modo | Comportamento | Melhor para |
|---|---|---|
| `hitl` | Human-in-the-loop. Pausa para revisão. | Aprendizado, task arriscada |
| `afk` | Autônomo. Segue sem pausa. | Trabalho em lote, baixo risco |

### Memory bridge

Arquivos PROGRESS persistem estado entre iterações: evita gasto de token com re-exploração,
registra decisões-chave, rastreia arquivos alterados, permite recovery de sessão após interrupção.

### Sync de contexto (step SYNC)

Ao terminar em `EXIT_COMPLETE`, o executor roda o `/sync-context` para checar drift entre
`CLAUDE.md`/`CONTEXT.md`/`AGENTS.md` e o código real — critério 7 da DoD
(`rules/definicao-de-pronto.md`). Em `CIRCUIT_BREAKER`/`MAX_ITERATIONS` o sync fica pendente e
é anotado no LOG. Em `--mode afk` o relatório vai para o LOG sem editar nada: a aplicação exige
confirmação humana. Drift de contexto nunca bloqueia a saída do loop.

## Recovery de sessão

Sessões agentic longas enfrentam: **context rot** (limite de token perde informação),
**timeout** (interrupção de rede/sistema), **interrupção humana** (usuário precisa pausar).
O memory bridge resolve isso com persistência automática de estado.

```bash
# Sessão interrompida? Retoma de onde parou:
/dev tasks/PROMPT_MINHA_TASK.md --resume
```

O executor: lê `progress/PROGRESS_{NOME}.md` → pula tasks já completas → restaura contexto de
decisões-chave → continua da próxima task incompleta.

### Arquivos de recovery

| Arquivo | Local | Propósito |
|---|---|---|
| PROGRESS | `progress/PROGRESS_{NOME}.md` | Log de iteração, decisões-chave, arquivos alterados |
| LOG | `logs/LOG_{NOME}_{TS}.md` | Relatório final de execução com estatísticas |

## Opções de comando

| Opção | Descrição |
|---|---|
| `--mode hitl` | Human-in-the-loop (padrão) — pausa para revisão |
| `--mode afk` | Autônomo — roda sem pausar |
| `--resume` | Retoma do arquivo PROGRESS existente |
| `--dry-run` | Valida e mostra o plano sem executar |
| `--max N` | Sobrescreve o máximo de iterações (padrão: 30) |

## Integração com agentes

Referencie qualquer agente deste harness com `@{nome}` dentro de uma task:

```markdown
### 🟡 CORE
- [ ] @kb-architect: Cria domínio KB de Redis
- [ ] @dbt-specialist: Cria model de staging
- [ ] @revisor-codigo: Revisa a implementação
```

Catálogo completo (sempre atualizado): `.claude/agents/README.md` — 25 agentes em 4 categorias
(`workflow/`, `architect/`, `dev/`, `data-engineering/`).

## Safeguards

| Safeguard | Padrão | Propósito |
|---|---|---|
| `max_iterations` | 30 | Previne loop infinito |
| `max_retries` | 3 | Tenta de novo task que falhou |
| `circuit_breaker` | 3 | Para se não houver progresso em N loops |
| `small_steps` | true | Uma mudança lógica por task |
| `feedback_loops` | [] | Comandos a rodar entre tasks |

## Dev Loop vs `/novo-projeto`

| Cenário | `/dev` (Dev Loop) | `/novo-projeto` (harness completo) |
|---|---|---|
| Domínio de KB novo | ✅ | |
| Protótipo | ✅ | |
| Feature única, isolada | ✅ | |
| Utilitário/parser | ✅ | |
| Feature multi-componente | | ✅ |
| Sistema em produção | | ✅ |
| Projeto de time | | ✅ |
| Trilha de auditoria completa (ADR, scorecard) | | ✅ |
| Input | `PROMPT.md` | `00-ideia.md` → ... → `tasks/{slug}/NN-*.md` |
| Crafting | `prompt-crafter` | `harness-brainstorm` → `harness-define` → `harness-design` |
| Estrutura | Flexível (1 arquivo) | Rígida (fases do `.claude/projetos/{slug}/`) |
| Gate obrigatório | Não (verificação por task, objetiva) | Sim (`/validar` + `revisor-codigo`) |
| Recovery | `PROGRESS.md` + `--resume` | `STATUS.md` do projeto |
| Uso típico | Tarefa de 1-4h | Multi-dia |

## Arquivos relacionados

| Arquivo | Propósito |
|---|---|
| `DEV-LOOP.md` (raiz) | Introdução e como usar |
| `.claude/commands/dev.md` | Definição do comando `/dev` |
| `.claude/agents/dev/prompt-crafter.md` | Agente de crafting |
| `.claude/agents/dev/dev-loop-executor.md` | Agente de execução |
| `.claude/dev/templates/PROMPT_TEMPLATE.md` | Template em branco |
| `.claude/dev/templates/PROMPT_EXAMPLE_FEATURE.md` | Exemplo: utilitário Python |
| `.claude/dev/templates/PROMPT_EXAMPLE_KB.md` | Exemplo: domínio de KB |
| `.claude/dev/examples/` | Exemplos reais acumulados neste repo |
| `.claude/skills/sync-context/SKILL.md` | Processo do step SYNC (fechamento do contexto) |

## Referências originais

- [11 Tips For AI Coding With Ralph Wiggum](https://www.aihero.dev/tips-for-ai-coding-with-ralph-wiggum) — Matt Pocock
- [Effective Harnesses for Long-Running Agents](https://www.anthropic.com/engineering/effective-harnesses-for-long-running-agents) — Anthropic

---

*Conceito "Dev Loop" originado em `bootcamp-zero-to-claude-code-prd/btc-zero-prd-claude-code`,
adaptado a este harness canônico.*
