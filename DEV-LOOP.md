# DEV-LOOP — execução ágil de tarefa pontual

> Conceito complementar ao fluxo principal do harness (`/novo-projeto` → `harness-*`).
> Para tarefa pontual de 1-4h, não para um projeto inteiro. Detalhe técnico completo em
> `.claude/dev/_index.md` — este arquivo é a introdução e o guia de uso.

---

## Introdução — o que é o Dev Loop

Todo trabalho com agente de código cabe num espectro de 3 níveis, do menos ao mais estruturado:

```
NÍVEL 1                    NÍVEL 2                       NÍVEL 3
Vibe coding                 Dev Loop                      Harness completo
───────────                 ────────                      ─────────────────
• Só prompt solto            • PROMPT.md dirigido           • 6 fases (00-ideia→05-retro)
• Sem estrutura               • Loop com verificação          • PRD + ADR + rastreabilidade
• Torce pra funcionar         • Prioridade RISKY→CORE→POLISH  • Gate obrigatório + revisor
                              • Memory bridge (recovery)      • Auditoria completa

Comando: (nenhum)            Comando: /dev                   Comando: /novo-projeto
Tempo: < 30 min               Tempo: 1-4 horas                Tempo: multi-dia
```

O **Dev Loop** ocupa o meio do espectro — é a resposta pra "eu não quero só um prompt solto,
mas também não preciso do fluxo inteiro de projeto (PRD, harness plan, tasks, scorecard) só
pra criar um domínio de KB ou um utilitário". Ele dá estrutura mínima e real: um arquivo
`PROMPT.md` com tasks priorizadas, verificação objetiva por exit code, e recovery de sessão —
sem o overhead de `.claude/projetos/{slug}/` inteiro.

Esse conceito foi trazido do projeto `bootcamp-zero-to-claude-code-prd` (que o chama de
"Agentic Development, nível 2") e adaptado à lógica deste harness canônico — os agentes agora
seguem nosso padrão de frontmatter simples, e o Dev Loop referencia diretamente os 25 agentes
já existentes aqui via `@nome`.

### Os dois agentes

| Agente | Quando entra em cena | O que faz |
|---|---|---|
| `prompt-crafter` | Você descreve a tarefa em linguagem natural | Explora o código, pergunta o que falta, gera o `PROMPT.md` |
| `dev-loop-executor` | Você já tem um `PROMPT.md` pronto | Executa as tasks em loop, verifica por exit code, salva progresso, gera log |

### O loop de execução

```
LOAD → VALIDATE → PICK (🔴 RISKY → 🟡 CORE → 🟢 POLISH) → EXECUTE → VERIFY → UPDATE → CHECK → LOOP → LOG → SYNC
```

Cada task é verificada por um **comando com exit code** — nunca por "parece que funcionou".
O estado é salvo a cada iteração num arquivo `PROGRESS.md` (o "memory bridge"), o que permite
retomar uma sessão interrompida (`--resume`) sem perder decisões já tomadas.

O último step, **SYNC**, fecha o ciclo de contexto: quando o loop termina em `EXIT_COMPLETE`, o
executor roda o `/sync-context` para checar se `CLAUDE.md`, `CONTEXT.md` e `AGENTS.md` ainda
descrevem o código que existe agora. É o critério 7 da DoD (`rules/definicao-de-pronto.md`) —
sem ele, dez rodadas de `/dev` deixam o contexto descrevendo um projeto que não existe mais.
O drift **nunca bloqueia** a saída do loop: em `--mode afk` o relatório vai para o LOG e a
aplicação fica pendente de confirmação humana.

---

## Como usar

### Opção 1 — deixar o crafter guiar (recomendado)

```bash
/dev "quero criar um parser de data que lida com múltiplos formatos"
```

O `prompt-crafter` explora o repo, faz perguntas direcionadas (escopo, quality tier, integração,
verificação, risco) e gera `.claude/dev/tasks/PROMPT_{NOME}.md` pronto pra executar.

### Opção 2 — executar um PROMPT já pronto

```bash
/dev tasks/PROMPT_DATE_PARSER.md
```

### Opção 3 — criar o PROMPT manualmente

```bash
cp .claude/dev/templates/PROMPT_TEMPLATE.md .claude/dev/tasks/PROMPT_MINHA_TASK.md
# edite o arquivo, depois:
/dev tasks/PROMPT_MINHA_TASK.md
```

### Opções de execução

| Opção | Efeito |
|---|---|
| `--mode hitl` | Human-in-the-loop (padrão) — pausa entre tasks para revisão |
| `--mode afk` | Autônomo — roda sem pausar |
| `--resume` | Retoma de onde parou, usando o `PROGRESS.md` salvo |
| `--dry-run` | Só valida a estrutura do PROMPT e mostra o plano — não executa nada |
| `--max N` | Sobrescreve o limite de iterações (padrão: 30) |

### Estrutura de um PROMPT.md

```markdown
# PROMPT: NOME

## Goal
Uma frase descrevendo o que "pronto" significa.

## Quality Tier
prototype | production | library

## Tasks (Prioritized)
### 🔴 RISKY (Do First)
- [ ] Decisão arquitetural ou ponto de integração incerto

### 🟡 CORE
- [ ] Implementação principal
- [ ] @nome-do-agente: task que precisa de um especialista

### 🟢 POLISH (Do Last)
- [ ] Limpeza, otimização

## Exit Criteria
- [ ] Verificação objetiva: `comando` (checado por exit code)

## Config
mode: hitl
max_iterations: 30
```

Referencie qualquer um dos 25 agentes deste harness com `@nome` dentro de uma task — catálogo
completo em `.claude/agents/README.md`.

### Recovery de sessão

Se a sessão travar, cair conexão, ou você precisar parar no meio:

```bash
/dev tasks/PROMPT_MINHA_TASK.md --resume
```

O executor lê `.claude/dev/progress/PROGRESS_{NOME}.md`, pula o que já está `[x]` no PROMPT, e
continua da próxima task incompleta — sem re-explorar o que já foi decidido.

### Onde tudo fica

```
.claude/dev/
├── tasks/       ← seus PROMPT_*.md (trabalho ativo)
├── progress/    ← memory bridge, auto-gerenciado
├── logs/        ← log de execução, auto-gerado ao concluir
├── templates/   ← PROMPT_TEMPLATE.md + 2 exemplos (feature, KB)
└── examples/    ← exemplos reais acumulados neste repo (começa vazio)
```

---

## Quando usar Dev Loop vs `/novo-projeto`

| Se a tarefa é... | Use |
|---|---|
| Criar/atualizar um domínio de KB | `/dev` |
| Protótipo rápido | `/dev` |
| Uma feature isolada, sem tocar em muitas partes | `/dev` |
| Utilitário ou parser | `/dev` |
| Projeto novo do zero (app/pipeline/agente) | `/novo-projeto` |
| Feature multi-componente com PRD próprio | `/novo-projeto` |
| Precisa de ADR, scorecard, trilha de auditoria completa | `/novo-projeto` |
| Gate (`/validar` + `revisor-codigo`) obrigatório antes de fechar | `/novo-projeto` |

Os dois fluxos não competem — o Dev Loop é a ferramenta certa pra quando o overhead do fluxo
completo de projeto não se paga. Nada impede usar `/dev` dentro de um projeto que já foi aberto
via `/novo-projeto`, pra uma tarefa pontual dentro dele.

---

## Telemetria live (fluxo-events)

Cada execução de `/dev` pode emitir metadados sob o slug sintético
`dev-loop-{nome}` (helper `slug_from_prompt_path` a partir de `PROMPT_*.md`).

- Painel: `.claude/projetos/dev-loop-{nome}/fluxo/live.html` (+ espelho `.cursor/`)
- Opcional: `python -m http.server 8765 --directory .claude/projetos/dev-loop-{nome}/fluxo` → `http://localhost:8765/live.html`
- Atalho: `/fluxo-live` · cheatsheet: `docs/cheatsheets/fluxo-events-cheatsheet.md`
- Mapa Dev Loop fases 0–6 (LOAD→…→SYNC); fail-soft (`|| true`)
- **`--dry-run` não emite** telemetria
- `EXIT_COMPLETE`: emit exit + `truncate --keep 100` + re-render
- Complementar a PROGRESS/LOG; **ortogonal** a evidence-gate (não unifica)

---

## Referências

- `.claude/dev/_index.md` — documentação técnica completa (todas as opções, formato de arquivo, pseudocódigo do loop)
- `.claude/agents/dev/prompt-crafter.md` — agente de crafting
- `.claude/agents/dev/dev-loop-executor.md` — agente de execução
- `.claude/commands/dev.md` — definição do comando `/dev`
- `.claude/skills/sync-context/SKILL.md` — step SYNC (fechamento do ciclo de contexto)
- `docs/cheatsheets/fluxo-events-cheatsheet.md` — telemetria live (SDD + Dev Loop)
- [11 Tips For AI Coding With Ralph Wiggum](https://www.aihero.dev/tips-for-ai-coding-with-ralph-wiggum) — Matt Pocock
- [Effective Harnesses for Long-Running Agents](https://www.anthropic.com/engineering/effective-harnesses-for-long-running-agents) — Anthropic

---

*Conceito originado em `bootcamp-zero-to-claude-code-prd/btc-zero-prd-claude-code`, adaptado a
este harness canônico.*
