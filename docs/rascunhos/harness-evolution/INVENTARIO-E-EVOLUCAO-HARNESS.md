# Inventário amplo do Agent Harness Canônico v2 e mapa de evolução

> **Documento de trabalho** para traçar um plano rumo a um harness próximo de 100% (referência: *Agent Engineering Harness — Eight Pillars*).  
> **Não é um plano de implementação imediato** para Custo nem Ontologia: esses anéis ficam registrados para o futuro.  
> **Data de consolidação:** 2026-08-27  
> **Repositório alvo:** `<raiz-do-clone>`  
> **Fontes locais:** `sketch/harness-evolution` (este clone `data-make-ppts-personal-tips-main`) + leitura direta do canônico.

---

## 1. Para que serve este documento

1. **Inventariar** tudo o que o canônico já tem (agents, skills, commands, rules, KBs, kernels, hooks, fluxos).
2. **Diagnosticar** os 8 anéis (Orchestration, Context, Memory, Tools, Reliability, Evaluation, Cost, Governance).
3. **Cruzar** o canônico com três motores de referência:
   - [Converge](https://github.com/fjmorais/converge) — coordenação, descent, settlement
   - [Seamwise](https://github.com/fjmorais/seamwise) — decomposição por seams / swimlanes / TaskPlan
   - [Task-Spec](https://github.com/luanmorenommaciel/task-spec) (fork esperado em `fjmorais/task-spec`) — contrato atômico, HMAC, eval, aceite independente
4. **Deixar um backlog de evolução** priorizado, sem misturar autoridade entre camadas.

**Fora de escopo permanente (já no `plan.md` original):** Dark Factory, monitoramento 24/7, auto-healing operacional de pipelines, PR automático para deploy em produção.

**Fora de foco agora (documentado, não implementar nesta fase):**

| Tema | Por que adiar | Onde está o backlog |
|------|----------------|---------------------|
| **Custo / budget-gate** | Assinatura Cursor sem API-KEY; sem token/$ no harness | Loop 4 (P1), §12 |
| **Ontologia de negócio** | Camada semântica first-class; depende de Context Builder | Loop 8 (P2), §13 |

---

## 2. O que o harness é (e o que não é)

O canônico é um **framework de governança de agentes** (Claude Code + Cursor), não um produto de aplicação.

| É | Não é |
|---|---|
| Fonte de agents, skills, KBs, rules, commands | Código de produto de negócio |
| Propagação via `/install-harness` (`install_harness.py` + `stack_map.json`) | Cópia manual de `.claude/` para filhos |
| Três níveis: vibe → Dev Loop → SDD 0–4 | Fábrica autônoma |
| Kernels YAML + engines Python em `config/` | Billing cloud, sandbox de execução, fleet Manager |
| Dual-runtime: `.claude/` espelhado em `.cursor/` | Bloqueio server-side (honesty **§1.3**) |

**Invariante de autoridade (a copiar de Converge):** *capacidade duplicada é aceitável; autoridade duplicada não.*  
O canônico hoje **acumula** papéis de decomposição, contrato de task, execução e aceite no mesmo fluxo (`to-tasks` + `harness-build` + `evidence-gate`). A evolução rumo a 100% deve **separar** esses papéis, não reinventar três CLIs dentro de `config/`.

---

## 3. Inventário — o que o canônico tem hoje

Contagens conferidas no clone em 2026-08-27 (README do canônico: 33 agents, 21 skills, 12 rules, 21 KBs, 24 commands).

### 3.1 Níveis de uso

```text
NÍVEL 1 — Vibe coding     prompt solto                         < 30 min
NÍVEL 2 — Dev Loop        /dev + PROMPT.md + exit code         1–4 h
NÍVEL 3 — Harness SDD     /novo-projeto + harness-*            multi-dia
```

### 3.2 Fluxo SDD (nível 3)

```text
/novo-projeto          → harness-brainstorm  → 00-ideia.md + STATUS.md + SI
/grill-me              → entrevista
harness-define         → 01-grill.md
/to-prd                → PRD.md → 02-prd.md
harness-design         → /harness-architect → 03-harness.md
/to-tasks              → tasks/{slug}/NN-*.md → 04-tasks-index.md
[/to-issues]           → GitHub Issues (opt-in)
harness-build          → /validar + revisor-codigo + evidence-gate + entregas.jsonl
harness-ship           → /sync-context + 05-retro.md + /scorecard
```

Checkpoints de `/novo-projeto`: `salvar-grill`, `salvar-prd`, `salvar-harness`, `salvar-tasks`, `shippar`.

Artefatos por projeto: `.claude/projetos/{slug}/` (espelho `.cursor/projetos/`).

### 3.3 Dev Loop (nível 2)

Ciclo: `LOAD → VALIDATE → PICK (RISKY→CORE→POLISH) → EXECUTE → VERIFY → UPDATE → CHECK → LOOP → LOG → SYNC`

| Peça | Path |
|------|------|
| Conceito | `DEV-LOOP.md` |
| Agentes | `prompt-crafter`, `dev-loop-executor` |
| PROMPT | `.claude/dev/tasks/PROMPT_*.md` |
| Recovery | `PROGRESS.md` (memory bridge) |
| Flags | `--mode hitl\|afk`, `--resume`, `--dry-run`, `--max N` (padrão 30) |
| Telemetria | slug sintético `dev-loop-{nome}` via `slug_from_prompt_path` |

### 3.4 Agents (33)

**workflow/** (ciclo de projeto + guias)

| Agente | Papel |
|--------|--------|
| `harness-brainstorm` | Ideia, SI, tipo de projeto |
| `harness-define` | Requisitos a partir do grill |
| `harness-design` | PRD + harness-architect |
| `harness-build` | Implementação task a task + emits fluxo |
| `harness-iterate` | Cascata consciente de mudança de fase |
| `harness-ship` | Close, scorecard, retro, truncate fluxo |
| `guia-brainstorm` / `guia-escopo` / `guia-roteiro` / `guia-etapas` / `guia-publish` / `guia-iterate` | Pipeline de guias didáticos |

**architect/**

`agent-creator`, `kb-architect`, `rag-architect`, `sql-architect`, `search-strategy-advisor`

**dev/**

`codebase-explorer`, `meeting-analyst`, `prompt-engineer`, `revisor-codigo`, `prompt-crafter`, `dev-loop-executor`

**data-engineering/**

`pipeline-architect`, `schema-designer`, `lakehouse-architect`, `data-platform-engineer`, `dbt-specialist`, `spark-engineer`, `sql-optimizer`, `streaming-engineer`, `data-contracts-engineer`, `data-quality-analyst`

Roteamento: só `description:` no frontmatter. Escalação está em `.claude/agents/README.md`.

### 3.5 Skills (21)

| Skill | Papel |
|-------|--------|
| `install-harness` | Propagação canônico → filho (`stack_map.json`) |
| `harness-architect` | Entrevista de stack → `.claude/` do alvo |
| `grill-me` / `grill-with-docs` | Entrevista de requisitos |
| `to-prd` / `to-tasks` / `to-issues` | Spec → PRD → tasks locais / Issues |
| `sync-context` | Drift CLAUDE/CONTEXT/AGENTS |
| `handoff` | Compactação de sessão (hoje grava em temp OS, não no projeto) |
| `new-adr` | ADRs imutáveis |
| `adversarial-judge` | Segundo modelo via OpenRouter (consultivo) |
| `write-a-skill` / `make-readme` / `gen-tests` | Metaprodução |
| `de-conformidade` / `cloud-secrets` | DE + vaults |
| `create-rag-pipeline` / `search-strategy-check` | RAG |
| `visual-explainer` / `excalidraw-diagram` / `guia-architect` | Visual / guias |

### 3.6 Commands (24)

**Raiz:** `/novo-projeto`, `/novo-guia`, `/dev`, `/nova-branch`, `/git-ajuda`, `/validar`, `/scorecard`, `/sync-context`, `/evidencias`, `/fluxo-live`

**data-engineering/:** `/pipeline`, `/schema`, `/data-quality`, `/lakehouse`, `/sql-review`, `/data-contract`, `/migrate`

**visual-explainer/:** `/generate-web-diagram`, `/generate-slides`, `/generate-visual-plan`, `/diff-review`, `/plan-review`, `/project-recap`, `/fact-check`

### 3.7 Rules (12, always-on + domain)

`agente`, `definicao-de-pronto`, `seguranca`, `git-hygiene`, `estilo-codigo`, `testes`, `backend`, `frontend`, `pipeline`, `rag`, `langgraph`, `multi-tenant`

DoD (`definicao-de-pronto.md`): gate `/validar` + evidence-gate + rules + revisor + critérios + ADR se contestável + `entregas.jsonl` + `/sync-context` no close do fluxo.

### 3.8 Knowledge bases (21 domínios)

`airflow`, `azure-keyvault`, `cloud-platforms`, `data-modeling`, `data-quality`, `databricks`, `dbt`, `design-instrucional`, `fastapi`, `lakehouse`, `langgraph`, `multi-tenant`, `observabilidade`, `oci-vault`, `pipeline`, `rag`, `spark`, `sql-patterns`, `streaming`, `supabase`, `testing`

Índice: `.claude/kb/_index.yaml` (limites de linhas; JIT — não carregar domínio inteiro).

### 3.9 Kernels (contratos YAML + engines)

| Kernel | Contrato | Engine | CLI | Semântica |
|--------|----------|--------|-----|-----------|
| Agent-policies | `agent-policies.yaml` | `config/agent_policies/` | `python -m config.agent_policies check\|generate` | deny-hard / ask em Bash |
| Evidence-gate | `evidence-gate.yaml` | `config/evidence_gate/` | `collect\|check` | prova mecânica por task |
| fluxo-events | `fluxo-events.yaml` | `config/fluxo_events/` | `emit\|render\|truncate` | telemetria fail-soft |
| Git hygiene | `git-hygiene.yaml` | `config/git_hygiene/` | `/nova-branch` | convenção + adapter Azure/GitHub |
| Data engineering | `data-engineering.yaml` | `config/canonical_data_check/` + `config/data_engineering/` | `validate\|baseline\|compare\|report\|explain` | pacotes A–E |

**Famílias core de agent-policies:** `shell`, `docker`, `git`, `sql-cli`, `databricks-cli`, `terraform`, `k8s`. Bypass consciente: `HARNESS_ALLOW_DESTRUCTIVE=1`.

**Evidence-gate:** manifesto `evidencias/tasks/<id>.yaml`, logs cap 2 MiB, `audit.jsonl` append-only, `evidencias_ref` obrigatório em `metrics/entregas.jsonl`. Ortogonal a `/validar` e a policies.

**fluxo-events:** mapas `sdd_map` 0–4 e `dev_loop_map` 0–6; live Opção C (`live.html`); `task_enter`/`task_exit`; IDs `event_id` / `run_id` / `parent_event_id`; seed KEEP em `.harness/fluxo-events/`.

**DE:** Universal (A) + yarn (B) + Airflow (C opcional) + Databricks FS (D) + Key Vault FS (E). Sem API live. `/validar` dispara data-check se marker **ou** SDP/DLT **ou** vault.

### 3.10 Hooks e git

| Runtime | Hook | Função |
|---------|------|--------|
| Claude | `PreToolUse` Bash | `agent_policies_pretooluse.sh` |
| Claude | `PostToolUse` Edit/Write | ruff format/fix em `backend`/`src` |
| Claude | `Stop` | ruff + mypy + pytest **se** existir `backend`/`src`; drift de contexto (aviso, 4 h) |
| Cursor | `beforeShellExecution` | `agent_policies_before_shell.sh` |
| Git | `.githooks/pre-commit` | heurística de segredos |
| Git | `commit-msg`, `pre-push` | convenção |

`settings.json` também materializa `permissions.deny` a partir das famílias.

### 3.11 MCP

`.mcp.json`: **Context-7** (docs oficiais) + **Postgres** placeholder `restricted`. Sem Tool Registry; servidores always-on no arquivo.

### 3.12 Install / foundation

`stack_map.json` propaga foundation always-on: CLAUDE/AGENTS/CONTEXT, kernels YAML, `config/`, hooks, seeds `.harness/policies`, `.harness/evidence-gate`, `.harness/fluxo-events`, commands de gate, etc. Categorias condicionais: `pipeline_dados`, `cloud_secrets`, stack da app.

Regra seed: `seed: true` → 1º COPY, re-install **KEEP**.

### 3.13 ADRs shipadas

| ADR | Decisão |
|-----|---------|
| 001 | Sync de contexto no fechamento |
| 002 | Pacote E keyvault dual |
| 003 | Kernel agent-policies dual-runtime |
| 004 | Kernel evidence-gate |
| 005 | Kernel fluxo-events |

**Ainda não existem:** ADR 006 memory-gate, 007 context, 008 eval-gate, 009 budget, 010 governance, 011 tool registry, 012 reliability, 013 ontologia.

Pendência conhecida: addendum Opção C da ADR 005 (não editar ADR existente).

### 3.14 Métricas

`metrics/entregas.jsonl`: critérios, gate (`tentativas_ate_verde`), revisor, `intervencoes_humanas`, commit, `evidencias_ref`. `/scorecard` deriva taxas; change-failure é lagging.

### 3.15 Dogfood recente (projetos no canônico)

Exemplos em `.claude/projetos/`: `pipeline-runtime-gates`, `medallion-sdd-gates`, `silver-checklist-odcs`, `fluxo-grafo-causal`, `visao-grafica-fluxo-agentes`, etc. Cada um com SDD 00–05 + evidências + (quando aplicável) `fluxo/live.html`.

---

## 4. Diagnóstico dos 8 anéis (consolidado do sketch)

Fonte: `plan.md` + decks `harness-evolution` / `harness-evolution-tecnico` (2026-08-21), revalidado contra o clone em 2026-08-27.

| Anel | Status | Já existe | Gap principal rumo a ~100% |
|------|--------|-----------|----------------------------|
| **Orchestration** | Forte | SDD 5 fases, Dev Loop, 33 agents, fluxo-events, `/novo-projeto` | State machine explícita; `cvg next` / next-pass a partir de evidência; barreira humana antes do build; review paralelo no close |
| **Context** | Parcial | Rules, 21 KBs, 21 skills, CLAUDE.md, `/sync-context`, skill `handoff` fraca | Context Builder por fase+task; HANDOFF de projeto (não temp OS); compaction; KB/MCP on-demand |
| **Memory** | Fraco | `tasks/`, `entregas.jsonl`, `projetos/`, PROGRESS.md só no Dev Loop | Memória cross-session (episódica + semântica); extract no ship; prefetch no build |
| **Tools** | Parcial | MCP, `/validar`, data-check, policies, hooks | Tool Registry; error shapes; dispatcher validate→execute; MCP always-on |
| **Reliability** | Parcial | Git hygiene, policies, evidence-gate, `--resume` Dev Loop | Checkpoints pós side-effect; idempotency; circuit breaker; Dev Loop durável além de PROGRESS.md |
| **Evaluation** | Parcial | `/validar`, revisor, evidence-gate, `/scorecard`, adversarial-judge opcional | Eval-gate com judge **independente e bloqueante**; golden set; CI de regressão do harness; aceite ≠ geração |
| **Cost** | Ausente | Proxies em `entregas.jsonl` | **Futuro** — §12 |
| **Governance** | Parcial | Policies locais, SI/LGPD em rules, githooks, GIT_PREFLIGHT | **§1.3:** gates locais contornáveis; branch protection; matriz propose/apply; PII scan |

Estimativa honesta de cobertura (subjetiva, para priorizar — não é métrica de CI):

```text
Orchestration  ~80%
Evaluation     ~55%
Governance     ~50%
Tools          ~50%
Reliability    ~45%
Context        ~40%
Memory         ~20%
Cost            ~5%   (adiado)
Ontologia       ~10%  (adiado; ODCS/KB qualidade existem, sem gate de negócio)

Média ponderada (sem Cost/Ontologia): ~48–55%
Alvo "muito próximo de 100%": fechar Memory + Context + Eval + autoridade de task
```

---

## 5. Referência externa — divisão de autoridade (Converge · Seamwise · Task-Spec)

Pin citado pelos READMEs (2026): **Converge 0.2.0**, **Seamwise 0.2.0**, **Task-Spec 3.8.0**.  
Converge **não importa** os engines: chama binários públicos (`CVG_TASKSPEC_BIN`, `CVG_SEAMWISE_BIN`).

### 5.1 Invariante

> **Seamwise decompõe. Task-Spec contrata. Converge coordena.**

| Sistema | É dono de | Não é dono de |
|---------|-----------|----------------|
| **Seamwise** | Seams, swimlanes, capability legs, topologia, review humano, `TaskPlan/v1` + lineage | Materializar tasks, dispatch, eval, aceite |
| **Task-Spec** | Validar TaskPlan, materializar folhas, HMAC/TIER=1, handoff, evals, `taskspec accept` | Descobrir iniciativa, decompor, loop de sessão, merge |
| **Converge** | Sequência entre engines, bind, loop limitado, settlement, receipts de composição | Autoridade interna de cada engine |
| **Humano** | Aceite de topologia Seamwise; risco explícito; stamp de gate | — |
| **Executor** | Mudança de código **dentro** do contrato | Auto-aceite |

Estados Seamwise relevantes: `DELIVERY_PLAN=NEEDS_REVIEW` → review receipt → `compile` → `task-plan.json` + `task-plan-lineage.json`. Chat **propõe**; não revisa.

Estados Converge compose: `NEEDS_REVIEW` → `PREVIEW_READY` → `MATERIALIZED` (folhas ainda `signed_off: false`).

Task-Spec 3.8 (síntese):

- Folha atômica: paths, comportamentos, evals, budget, owner
- `taskspec gate --stamp` → `TIER=1` (HMAC v3 sobre `TaskRevision/v1`)
- `TaskHandoff/v3` (attempt UUID, git base, closure)
- `taskspec accept` reroda prova; só POST-gate escreve `accepted*`
- `taskspec demo` prova o ciclo isolado
- Instalador projeta skill em `.agents/`, `.claude/`, `.grok/` — **sem dest Cursor nativo** no Converge `install.sh`

Descent Converge: **duas fases, uma barreira**. Pass 4 (adversarial / consensus) é o último sign-off humano antes da máquina.

Onze skills Converge + Tasking standalone (Pass 5). Utilitário `evidence-to-next-pass` (`cvg next`) deriva o próximo passo de evidência de workspace — evidência **não** é veredito; o gate decide.

### 5.2 Mapa Pass Converge → canônico hoje

| Pass | Converge | Canônico equivalente | Lacuna |
|------|----------|----------------------|--------|
| 0 | `idea-to-brd` / `cvg capture` | `harness-brainstorm` + `/grill-me` | Sem BRD formal / `CHECK_BRD` |
| 1 | tech-spec verificável | `harness-define` + `/to-prd` | Requisitos nem sempre falsificáveis |
| 2 | ADRs de grounding | `/new-adr` ad hoc | Sem pass de grounding sistemático contra o repo |
| 3 | swimlanes / seams | `/to-tasks` (tracer bullets) | Sem seams, sem TaskPlan, sem lineage |
| 4 | adversarial + **THE BARRIER** | `adversarial-judge` opcional | Consultivo; **não bloqueia** build |
| 5 | Task-Spec TIER=1 | Markdown `tasks/{slug}/NN-*.md` | Sem HMAC, sem evals selados, sem `signed_off` |
| 6 | issues tracker | `/to-issues` opt-in | Sem `blocked-by` mecânico no tracker |
| 7 | runtime contract + brief | implícito em `harness-build.md` | Sem `cvg bind` / contrato runtime |
| 8 | task-loop até eval GREEN + PR | `harness-build` / `/dev` | Loop não é eval-bounded; PR não é settlement |
| util | `cvg next` | `STATUS.md` + fluxo-events | Sequenciador não deriva o próximo pass de artefatos |
| settle | `cvg verify` + receipts | evidence-gate + scorecard | Local e forjável (§1.3); sem judge de família diferente no close |

### 5.3 O que **não** copiar

- Vendorar código de Seamwise/Task-Spec dentro de `config/`
- Fazer o agent “aceitar” a própria entrega
- Tratar narrativa de modelo como evidência de settlement
- Instalar skill espelho de Task-Spec no Converge (eles recusaram de propósito)
- Esperar dest Cursor do `install.sh` do Converge — o canônico precisa de um **adaptador Cursor** (já tem `.cursor/`)

### 5.4 O que **adotar como padrão de desenho**

1. **CLI JSON estável** (`--json`, `--dry-run`, tokens `CHECK_*=PASS`, `TIER=1`).
2. **Receipts com digest** (plan, review, task, handoff).
3. **Fail closed** em review stale (Seamwise: compile recusa sem receipt do digest atual).
4. **Uma barreira humana** entre design e execução.
5. **Aceite independente** (outro processo, outro contexto, preferencialmente outro modelo).
6. **Ortogonalidade de kernels** (o canônico já faz isso bem: policies ≠ evidence ≠ fluxo ≠ `/validar`).

---

## 6. Gaps por anel — o que falta para chegar perto de 100%

### 6.1 Orchestration (manter + refinar)

**Já forte.** Evolução:

- Documento `docs/sdd-transitions.md`: o que é código vs LLM em cada transição 0→4.
- State machine explícita (estados nomeados tipo `COMPOSE=` / `DELIVERY_PLAN=`), não só prosa de agent.
- Condutor tipo `evidence-to-next-pass`: dado `projetos/{slug}/`, dizer o próximo comando **sem** waiver de gate.
- Wiring completo de `task_enter`/`task_exit` (hoje depende do agent seguir `harness-build.md`).
- Review paralelo no close (revisor + evidence-gate + opcional eval-judge) sem serializar tudo no mesmo chat.

**Não fazer:** Manager fleet (Converge também declara fora de v0.2.0).

### 6.2 Context (P0 — Loop 2)

**Hoje:** contexto estático (rules/KBs always-on); skill `handoff` grava fora do workspace; `/sync-context` só no close.

**Alvo:**

| Camada | Comportamento |
|--------|----------------|
| Write | Decisões em ADR / STATUS / HANDOFF de projeto |
| Select | KB e skills montados por fase + task (índice `_index.yaml` já existe) |
| Compress | Nova sessão com HANDOFF + task atual, não chat infinito |
| Isolate | Dev Loop ≠ SDD; memória de task ≠ CLAUDE.md |

Template mínimo de HANDOFF de projeto (do `passo-a-passo.md`):

```markdown
# HANDOFF — {fase} — {data}
## Decisões tomadas
## Pendências
## Arquivos alterados
## Próximo passo
```

Skill `context-handoff` deve **escrever em** `.claude/projetos/{slug}/HANDOFF.md` (ou raiz do filho), não no temp do SO.

**Não neste loop:** compaction automática via LLM em runtime.

### 6.3 Memory (P0 — Loop 1) — começar por aqui

**Hoje:** conhecimento morre na sessão; Dev Loop tem PROGRESS.md; SDD não.

Camadas mínimas (do `plan.md`):

```yaml
working:    janela atual (efêmera)
episodic:   .harness/memory/sessions.jsonl
semantic:   .harness/memory/MEMORY.md
procedural: candidatos a skill/KB (revisão humana)
```

CLI sugerida: `prefetch | append | extract`. Hook pós-`harness-ship` para 3 bullets (funcionou / falhou / não repetir).

**Não neste loop:** embeddings, vector DB, sync cross-machine.

Ação manual já possível (antes do kernel): criar `MEMORY.md` e ler no enter de `harness-build`.

### 6.4 Tools (P1 — Loop 6)

**Hoje:** MCP always-on; policies cobrem Bash, não o catálogo de tools do agente.

Alvo: registry JSON + dispatcher `validate → execute`; error shapes `retryable | permission | schema_violation`; tools de escrita exigem escalação; mount on-demand **depois** do Context Builder.

Scripts: exit `0` ok, `1` retryable, `2` fatal.

### 6.5 Reliability (P1 — Loop 7)

**Hoje:** `--resume` + PROGRESS.md; policies; git hygiene. Sem idempotency keys nem circuit breaker.

Alvo: checkpoint após side-effect; estado Dev Loop em `.claude/dev/progress/`; se `/validar` falhar 3× na mesma task → parar (hoje regra manual).

Depende do Loop 2 (handoff).

### 6.6 Evaluation (P0 — Loop 3)

**Hoje:** `/validar` (lint/type/test) ≠ aceite de comportamento da task; revisor no **mesmo** runtime; judge OpenRouter **não bloqueia**; evidence-gate prova comando/exit, não rubrica de qualidade do harness.

Alvo alinhado a Task-Spec:

- Geração ≠ avaliação (POST-gate separado)
- Golden cases por tipo (DE, infra, refactor)
- Agent `eval-judge` que **não** herda a narrativa do builder (chat novo ou modelo de outra família)
- CI: `make test` + eval; regressão se score cair
- Amarrar eval-gate no close junto com evidence-gate

**Não neste loop:** eval online em produção, ensemble multi-modelo.

Ação manual hoje: close → collect/check → `/validar` → **novo chat** com diff + critérios → veredito.

### 6.7 Governance (P1 — Loop 5)

**Hoje:** §1.3 honesto — sem Edit policies / branch protection, nada impede de fato; `--no-verify` e clone sem hooks contornam; `HARNESS_ALLOW_DESTRUCTIVE` existe.

Alvo: matriz propose / apply / PR / deny por risco; expandir famílias (Airflow prod, writes UC); skill PII/LGPD scan; correlacionar evidence + fluxo + entregas; playbook Azure/GitHub **fora** do código.

Ação manual hoje: `/nova-branch`; proteger `main`; nunca PII no chat; deploy só via PR humano.

---

## 7. Loops SDD de evolução (ordem)

Princípio: **um loop = um kernel ou pacote coeso**. Cadência igual à do canônico:

```text
0 IDEIA (ADR) → 1 REQUISITOS (YAML) → 2 DESIGN (config/) → 3 IMPLEMENTAR (CLI+tests) → 4 ENCERRAR (cheatsheet + install)
```

| Loop | Anel | Prioridade | Foco agora? |
|------|------|------------|-------------|
| 1 `memory-gate` | Memory | P0 | **Sim** |
| 2 Context Builder + handoff | Context | P0 | **Sim** (depois do 1) |
| 3 `eval-gate` | Evaluation | P0 | **Sim** |
| 4 `budget-gate` | Cost | P1 | **Não** — só documentado |
| 5 Governance reforçada | Governance | P1 | Depois do P0 |
| 6 Tool Registry | Tools | P1 | Depois do Loop 2 |
| 7 Reliability dev-session | Reliability | P1 | Depois do Loop 2 |
| 8 Ontologia de negócio | Context+Memory | P2 | **Não** — só documentado |

**Ordem:** `1 → 2 → 3` (P0). Depois `5, 6, 7` em paralelo onde possível. `4` e `8` no futuro.

Dependências:

```text
Loop 1 (memory)
    └── Loop 2 (context / prefetch)
            ├── Loop 6 (tools on-demand)
            ├── Loop 7 (handoff + checkpoints)
            └── Loop 8 (ontologia)  [futuro]
Loop 3 (eval) — independente após Loop 1 mínimo
Loop 4 (budget) — independente; eventos em fluxo-events  [futuro]
Loop 5 (governance) — expande agent-policies
```

Evoluir **em cima** dos kernels:

| Kernel atual | Extensão natural |
|--------------|------------------|
| `agent-policies` | Loop 5 |
| `evidence-gate` | Loop 3 (eval no close) |
| `fluxo-events` | Loop 4 (budget_warning) no futuro; Orchestration (next-pass) |
| `canonical_data_check` | Loop 8 (contrato/ontologia DE) no futuro |
| `/install-harness` | Todos os loops (foundation + seed KEEP) |

---

## 8. Como o canônico deve “ficar o melhor possível” sem virar um Converge interno

Estratégia recomendada (SOLID aplicado a harness):

| Princípio | Aplicação |
|-----------|-----------|
| **S** | Um kernel, uma autoridade (não misturar memory + eval no mesmo YAML) |
| **O** | Novos passes como adapters que **chamam** `seamwise` / `taskspec` / `cvg` se forem adotados, sem fork do engine |
| **L** | Qualquer executor (Claude, Cursor, Codex) recebe o **mesmo** contrato de task |
| **I** | Interfaces pequenas: `prefetch`, `check`, `stamp`, `accept` — não um “harness-god CLI” |
| **D** | Agents dependem de contratos YAML/CLI, não do miolo uns dos outros |

**Três opções de integração (decisão futura, não neste documento de inventário):**

1. **Composição externa (preferível):** instalar Task-Spec + Seamwise + opcionalmente Converge no PATH; o canônico vira o dest Cursor + DE + policies. Passes 3–8 do descent passam a ser binários.
2. **Compatibilidade de artefatos:** `/to-tasks` passa a emitir (ou validar) `TaskPlan/v1` sem materializar; materialização fica no `taskspec batch`.
3. **Reimplementação** — **evitar.** Duplica autoridade e atrasa o 100%.

Se a opção 1 for escolhida depois: o canônico continua dono de **DE, install-harness, fluxo-events, agent-policies, KBs PT-BR**. Converge continua dono de **sequência e settlement**. Não criar `cvg` paralelo em Python.

---

## 9. Benefício por fase SDD (quando os loops P0 existirem)

| Fase | Agentes | O que ganha |
|------|---------|-------------|
| 0 IDEIA | `harness-brainstorm` | Prefetch de MEMORY (projetos similares) |
| 1 REQUISITOS | `grill-me`, `harness-define` | HANDOFF; (ontologia só no Loop 8) |
| 2 DESIGN | `harness-design`, architect | Context Builder; tools on-demand (Loop 6) |
| 3 BUILD | `harness-build`, `revisor-codigo` | Memory extract parcial; eval-gate; policies |
| 4 SHIP | `harness-ship`, `/scorecard` | Lesson extraction; eval score |

---

## 10. Passo a passo prático **hoje** (sem kernels novos)

Copiado e unificado do `passo-a-passo.md` / deck técnico. Cursor, sem API-KEY.

| Anel | Faça nesta semana |
|------|-------------------|
| Orchestration | Abrir `/fluxo-live`; emitir enter/exit por task; close = `/validar` → revisor → `evidence_gate check` |
| Context | HANDOFF ao fim de cada fase; nova sessão só com HANDOFF + task; citar `@kb/...` pontual |
| Memory | Criar `.harness/memory/MEMORY.md` (Decisões / Erros / Convenções); 3 bullets no ship |
| Tools | Enxugar `.mcp.json`; `agent_policies check` antes de shell arriscado |
| Reliability | Commit parcial antes de destrutivo; `--resume`; 3 fails → parar |
| Evaluation | Evidence collect/check; revisor em **chat novo** |
| Cost | *(adiado)* limites manuais 15 turns / 90 min — ver §12 |
| Governance | `/nova-branch`; PII fora do chat; prod só PR humano |

---

## 11. Critério de “muito próximo de 100%” (definição operacional)

Um harness está **perto de 100%** neste contexto quando:

1. Toda unidade de trabalho tem **contrato selado** (paths, evals, owner) antes de executar.
2. Existe **barreira humana** entre decomposição e dispatch.
3. **Aceite** é um processo separado da geração (eval + worktree + histórico).
4. Contexto da sessão é **montado**, não dumpado.
5. Memória de erros/decisões **sobrevive** à sessão.
6. Tools têm contrato e falham de forma classificável.
7. Recovery não reexecuta side-effect.
8. Gates locais são honestos (§1.3) **e** há pelo menos um controle server-side (branch protection) documentado.
9. Telemetria explica o fluxo mas **não** substitui DoD.
10. DE permanece first-class (data-check A–E) sem misturar com settlement de task.

Itens 8 (server-side) e a parte de Cost não são necessários para declarar P0 completo.

---

## 12. Backlog futuro — Custo (não implementar agora)

**Problema:** sessões longas sem limite; Cursor é assinatura, não há $ por token no harness.

**Não calcular $/token.** Usar limites e eficiência.

Práticas manuais (já no deck técnico):

- Máx. ~15 interações de agente por task
- Sessão > 90 min → HANDOFF e parar
- Modelo rápido no `/dev`; forte só design/review
- Proxies: `tentativas_ate_verde`, `intervencoes_humanas`
- Planilha: `R$ assinatura ÷ tasks fechadas/mês`
- Cursor Settings → Usage (premium requests), quando disponível

**Loop 4 (quando for a hora):** ADR 009; `budget-gate.yaml` com `max_turns` / `max_minutes`; soft-warning + hard-stop; eventos `budget_warning` / `budget_exhausted` no fluxo-events; CLI `check | status`; campo opcional `custo_estimado` em `entregas.jsonl`. **Sem** model routing automático nesse loop. **Sem** campo dólar obrigatório.

---

## 13. Backlog futuro — Ontologia de negócio (não implementar agora)

**Problema:** harness técnico forte; semântica de negócio não é first-class.

Já existe vizinho: KB `data-quality` (ODCS), skill `/data-contract`, padrão `silver-checklist-odcs`, gate DE.

**Loop 8 (quando for a hora):** ADR 013; KB `ontologia-negocio`; skill `business-context` (entrevista dor → fontes → semântica); gate em `harness-define` antes de `harness-design`; grafo em markdown/mermaid no PRD; `/validar` falha sem contrato quando marker DE. **Não** grafo runtime / embeddings neste loop.

Depende do Loop 2 (Context Builder).

---

## 14. Sugestão de desenho melhor (quando for implementar kernels)

Padrão já vencedor no canônico — **repetir**, não inventar outro:

```text
<nome>.yaml                 # contrato versionado (fonte única)
config/<nome>_gate/         # load, match/run, cli, templates seed
tests/<nome>_gate/          # pytest hermético
docs/<nome>-cheatsheet.md   # 1 página + §1.3
.harness/<nome>/            # seed KEEP no filho
install stack_map           # foundation ou categoria
espelho .cursor/            # mesma sessão
```

CLI máquina (inspirado em Converge/Seamwise/Task-Spec):

```text
python -m config.memory_gate --json prefetch --slug {slug}
# { "ok": true, "token": "MEMORY=READY", "artifacts": [...], "next": [...] }
```

Evitar: agent “officer” por kernel (já recusado em policies/evidence/fluxo).  
Evitar: Stop hook que quebra SDD em repo sem `backend/`/`src/` de forma surpresa (hoje o Stop já no-op sem essas pastas — manter essa honestidade).

Integração Task-Spec (melhor que markdown solto):

```text
# futuro — ilustrativo
taskspec plan --manifest seamwise/task-plan.json
taskspec batch
taskspec gate --stamp tasks/T-....md
taskspec handoff --backend cursor --out ...
# executor no contrato
taskspec accept --handoff ... --stamp
```

Cursor: mapear `--backend cursor` para o dest `.cursor/skills/` (o canônico já espelha skills).

---

## 15. Próximo passo recomendado (P0)

1. ADR **006** — `memory-gate` (Loop 1, Fase 0).  
2. Branch `feat/memory-gate` via `/nova-branch`.  
3. Fechar Fases 1–4 do Loop 1 **antes** de abrir Loop 2.  
4. Em paralelo (sem código): decidir se a decomposição futura será **Seamwise binário** ou evolução de `/to-tasks` (decisão de autoridade — não misturar no Loop 1).

---

## 16. Fontes e evidência

| Fonte | Tipo | Uso |
|-------|------|-----|
| `plan.md`, `passo-a-passo.md` (sketch original) | Direto | Loops e passos práticos |
| Decks `harness-evolution` e `harness-evolution-tecnico` | Direto | Diagnóstico por anel |
| `README.md`, `CLAUDE.md`, `CONTEXT.md`, `HARNESS-GUIDE.md`, `DEV-LOOP.md` do canônico | Direto | Inventário |
| Glob de `.claude/{agents,skills,commands,rules,kb}` | Direto | Contagens |
| ADRs 001–005, kernels YAML, `stack_map.json`, `.mcp.json`, `settings.json` | Direto | Gates e hooks |
| README Converge 0.2.0 (GitHub `fjmorais/converge`) | Reportado | Autoridade e descent |
| README Seamwise 0.2.0 (GitHub `fjmorais/seamwise`) | Reportado | TaskPlan / review |
| README Task-Spec 3.8.0 (`luanmorenommaciel/task-spec@v3.8.0`) | Direto (raw) | Contrato HMAC/eval/accept |
| `https://github.com/fjmorais/task-spec` | Limitação | Fetch 404 nesta sessão — tratar como fork esperado do upstream 3.8 |

**Limitação:** este documento não executou `make test` no canônico nem `taskspec demo` / `cvg compose`. Comportamento de CLIs externas é o declarado nos READMEs.

---

## 17. Índice rápido de paths no canônico

```text
CLAUDE.md AGENTS.md CONTEXT.md HANDOFF.md HARNESS-GUIDE.md DEV-LOOP.md
install-harness
agent-policies.yaml evidence-gate.yaml fluxo-events.yaml
data-engineering.yaml git-hygiene.yaml
config/{agent_policies,evidence_gate,fluxo_events,canonical_data_check,git_hygiene,data_engineering}/
.claude/{agents,skills,commands,rules,kb,hooks,dev,projetos,guias,design}/
.cursor/  (espelho)
.mcp.json .claude/settings.json .cursor/hooks.json
.githooks/
metrics/entregas.jsonl
docs/adr/ docs/*-cheatsheet.md
tasks/{slug}/NN-*.md
examples/{spark-yarn-airflow-min,databricks-sdp-min,databricks-dlt-min,keyvault-*}
```

---

*Fim do inventário. Use este arquivo como input de um `/define` ou ADR 006 — não como spec já aceita.*
