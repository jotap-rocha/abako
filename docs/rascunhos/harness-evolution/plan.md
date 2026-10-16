# Plano de Evolução — Agent Harness Canônico v2

> **Escopo:** melhorar o harness para **construir projetos com IA** de forma mais segura,
> consistente e repetível.  
> **Fora de escopo:** Dark Factory, monitoramento autônomo 24/7, auto-healing operacional de
> pipelines, PR automático para deploy em produção.

**Repositório alvo:** `<raiz-do-clone>`  
**Referência de anéis:** [Agent Engineering Harness — Eight Pillars](https://cubxxw.com/ai-agent/posts/agent-engineering-the-98-percent-harness/)  
**Data:** 2026-08-21

---

## 1. Diagnóstico — estado atual dos 8 anéis

| Anel | Status | Já implementado | Gap principal |
|------|--------|-------------------|---------------|
| **Orchestration** | ✅ Forte | SDD 5 fases, Dev Loop, 33 agents, `fluxo-events` | State machine explícita; review paralelo no close |
| **Context** | ⚠️ Parcial | Rules, 21 KBs, 21 skills, `CLAUDE.md` | Sem Context Builder, compaction, handoff estruturado |
| **Memory** | ❌ Fraco | `tasks/`, `entregas.jsonl`, `projetos/` | Sem memória cross-session; erros se repetem |
| **Tools** | ⚠️ Parcial | MCP, `/validar`, `data-check`, hooks | Sem Tool Registry formal; MCP always-on |
| **Reliability** | ⚠️ Parcial | `agent-policies`, `evidence-gate`, git hygiene | Sem checkpoints, idempotency, circuit breaker |
| **Evaluation** | ⚠️ Parcial | `/validar`, revisor, evidence-gate, `/scorecard` | Sem eval-gate, judge independente, regressão CI |
| **Cost** | ❌ Ausente | — | Sem budget-gate, routing, métrica por entrega |
| **Governance** | ⚠️ Parcial | Policies locais, SI/LGPD em rules | §1.3: gates locais contornáveis |

**Kernels já shipados (ADRs 003–005):** `agent-policies`, `evidence-gate`, `fluxo-events`, `canonical_data_check`.

---

## 2. Princípio de implementação

Cada evolução é entregue como **Loop SDD** no próprio canônico — mesma cadência que o harness
já usa para evoluir features:

```
Loop N
├── Fase 0 — IDEIA        → ADR + problema delimitado
├── Fase 1 — REQUISITOS   → contrato YAML + critérios de aceite
├── Fase 2 — DESIGN       → kernel em config/ + seed + install
├── Fase 3 — IMPLEMENTAR  → CLI + tests + wiring agents/commands
└── Fase 4 — ENCERRAR     → cheatsheet + propagate install-harness + retrospectiva
```

**Regra:** um loop = **um kernel ou um pacote coeso**. Não misturar memory + eval no mesmo loop.

---

## 3. Loops de evolução (ordem recomendada)

### Loop 1 — `memory-gate` (anel Memory) — P0

**Problema:** conhecimento morre na sessão; projetos multi-dia repetem erros.

| Fase SDD | Entregáveis | Critério de sucesso |
|----------|-------------|---------------------|
| **0 — Ideia** | ADR 006; escopo: episodic + semantic mínimo | ADR aceita; escopo ≤ 1 kernel |
| **1 — Requisitos** | `memory-gate.yaml`; schema `.harness/memory/` | Contrato versionado; camadas definidas |
| **2 — Design** | `config/memory_gate/` (load, append, prefetch, extract) | Seed `KEEP` via install; orthogonality documentada |
| **3 — Implementar** | CLI `prefetch \| append \| extract`; hook pós-`harness-ship` | Testes pytest; lesson extraction em ship |
| **4 — Encerrar** | Cheatsheet; wiring `harness-build`/`harness-ship` | Re-install propaga; retrospectiva no canônico |

**Camadas mínimas:**

```yaml
working:    janela atual (efêmera)
episodic:   .harness/memory/sessions.jsonl
semantic:   .harness/memory/MEMORY.md
procedural: candidatos a skill/KB (manual review)
```

**Não fazer neste loop:** embeddings, vector DB, sync cross-machine.

---

### Loop 2 — Context Engineering (anel Context) — P0

**Problema:** contexto estático (rules/KBs sempre carregados); sessões longas degradam.

| Fase SDD | Entregáveis | Critério de sucesso |
|----------|-------------|---------------------|
| **0 — Ideia** | ADR 007; depende de Loop 1 (prefetch memória) | ADR referencia memory-gate |
| **1 — Requisitos** | Spec Context Builder; política de compaction | Documento com 4 estratégias: write/select/compress/isolate |
| **2 — Design** | Template `HANDOFF.md`; skill `context-handoff` | Handoff entre fases SDD padronizado |
| **3 — Implementar** | Context Builder em `harness-build`/`harness-define` | KB/tools montados por fase+task, não always-on |
| **4 — Encerrar** | Guia HTML ou cheatsheet; update agents workflow | Agents citam handoff no exit de fase |

**Não fazer neste loop:** compaction automática via LLM em runtime (só spec + handoff manual primeiro).

---

### Loop 3 — `eval-gate` (anel Evaluation) — P0

**Problema:** gate verde ≠ regressão; mudança no harness não tem prova mecânica.

| Fase SDD | Entregáveis | Critério de sucesso |
|----------|-------------|---------------------|
| **0 — Ideia** | ADR 008; escopo: eval offline + judge separado | Separação geração ≠ avaliação explícita |
| **1 — Requisitos** | `eval-gate.yaml`; rubricas por tipo (DE, infra, refactor) | ≥ 3 casos golden por rubrica |
| **2 — Design** | `config/eval_gate/`; agent `eval-judge` (workflow/) | Judge não herda narrativa do builder |
| **3 — Implementar** | CLI `run \| report`; CI no canônico (`make test` + eval) | Regressão falha se score cair |
| **4 — Encerrar** | Integração evidence-gate no close; `/scorecard` estendido | Métrica eval por entrega |

**Não fazer neste loop:** eval online em produção, multi-model ensemble.

---

### Loop 4 — `budget-gate` (anel Cost) — P1

**Problema:** sessões longas sem limite de turns/tokens/$.

| Fase SDD | Entregáveis | Critério de sucesso |
|----------|-------------|---------------------|
| **0 — Ideia** | ADR 009 | Escopo: contador local, não billing cloud |
| **1 — Requisitos** | `budget-gate.yaml`; limites por sessão e por slug | Schema com soft-warning + hard-stop |
| **2 — Design** | `config/budget_gate/`; integração fluxo-events | Evento `budget_warning` / `budget_exhausted` |
| **3 — Implementar** | CLI `check \| status`; hook pre-turn nos agents | Loop para quando budget estoura |
| **4 — Encerrar** | Campo `custo_estimado` em `entregas.jsonl` (opcional) | Scorecard exibe custo por entrega |

**Não fazer neste loop:** model routing automático (Loop 4b futuro).

---

### Loop 5 — Governance reforçada (anel Governance) — P1

**Problema:** §1.3 — gates locais contornáveis.

| Fase SDD | Entregáveis | Critério de sucesso |
|----------|-------------|---------------------|
| **0 — Ideia** | ADR 010; matriz propose/apply por risco | Tabela: auto / ask / PR / deny |
| **1 — Requisitos** | Expandir `agent-policies.yaml`; doc branch protection | Novas famílias (Airflow prod, writes UC) |
| **2 — Design** | Playbook Azure DevOps/GitHub Edit policies | Passo a passo fora do código |
| **3 — Implementar** | PII/LGPD scan skill; audit trail unificado | evidence + fluxo + entregas correlacionados |
| **4 — Encerrar** | Update `seguranca.md`; guia `06-seguranca.html` | §1.3 atualizado com o que ficou server-side |

**Não fazer neste loop:** tag `prod-*` (já marcada Fase 2 git hygiene).

---

### Loop 6 — Tool Registry (anel Tools) — P1

**Problema:** tools sem contrato formal; MCPs carregados em excesso.

| Fase SDD | Entregáveis | Critério de sucesso |
|----------|-------------|---------------------|
| **0 — Ideia** | ADR 011 | Escopo: registry + dispatcher, não novos MCPs |
| **1 — Requisitos** | Schema tool JSON; error shapes padronizados | `retryable`, `permission`, `schema_violation` |
| **2 — Design** | `config/tool_registry/`; mount on-demand por task | Integração Context Builder (Loop 2) |
| **3 — Implementar** | Dispatcher validate → execute; tests | Unknown tool → erro retryable |
| **4 — Encerrar** | Update MCP docs; install propaga registry | Tools de escrita exigem escalação |

---

### Loop 7 — Reliability dev-session (anel Reliability) — P1

**Problema:** recovery de sessão de dev, não de pipeline.

| Fase SDD | Entregáveis | Critério de sucesso |
|----------|-------------|---------------------|
| **0 — Ideia** | ADR 012 | Escopo: Dev Loop durável + checkpoints pós side-effect |
| **1 — Requisitos** | Política checkpoint por consequência | Lista o que checkpoint vs recompute |
| **2 — Design** | Estado Dev Loop em `.claude/dev/progress/` | Retomar PROMPT após crash |
| **3 — Implementar** | Idempotency keys em commands destrutivos; circuit breaker | Retry não repete side effect |
| **4 — Encerrar** | Update `DEV-LOOP.md`; testes recovery | Dev Loop retoma de estado consistente |

---

### Loop 8 — Ontologia de negócio (anel Context + Memory) — P2

**Problema:** harness técnico forte; camada semântica/negócio não é first-class.

| Fase SDD | Entregáveis | Critério de sucesso |
|----------|-------------|---------------------|
| **0 — Ideia** | ADR 013 | Escopo: KB + skill + gate define, não grafo runtime |
| **1 — Requisitos** | KB `ontologia-negocio`; skill `business-context` | Template entrevista dor→fontes→semântica |
| **2 — Design** | Gate em `harness-define`: ontologia mínima | Checklist antes de `harness-design` |
| **3 — Implementar** | Grafo de dependências em markdown/mermaid no PRD | Nós/arestas documentados por projeto |
| **4 — Encerrar** | Integração data contracts ODCS como gate DE | `/validar` falha sem contrato quando marker DE |

---

## 4. Mapa — anel × loop SDD de implementação

| Anel | Loop(s) | Prioridade |
|------|---------|------------|
| Memory | Loop 1 | P0 |
| Context | Loop 2, Loop 8 | P0 / P2 |
| Evaluation | Loop 3 | P0 |
| Cost | Loop 4 | P1 |
| Governance | Loop 5 | P1 |
| Tools | Loop 6 | P1 |
| Reliability | Loop 7 | P1 |
| Orchestration | Transversal (wiring em cada loop) | — |

---

## 5. Mapa — evolução × fase SDD de **uso** (quando o harness estiver evoluído)

O que cada fase SDD **ganha** quando os loops estiverem shipados:

| Fase SDD | Agentes | Loops que beneficiam | Capacidade nova |
|----------|---------|----------------------|-----------------|
| **0 — IDEIA** | `harness-brainstorm` | L2, L8 | Contexto inicial + memória de projetos similares |
| **1 — REQUISITOS** | `grill-me`, `harness-define` | L1, L2, L8 | Ontologia mínima; prefetch memória; handoff |
| **2 — PRD_HARNESS** | `harness-design`, `harness-architect` | L2, L6 | Context Builder; tools on-demand |
| **3 — IMPLEMENTAR** | `harness-build`, `revisor-codigo` | L1, L3, L4, L5, L7 | Memory extract; eval-gate; budget; policies |
| **4 — ENCERRAR** | `harness-ship`, `/scorecard` | L1, L3, L4 | Lesson extraction; eval score; custo por entrega |

---

## 6. Dependências entre loops

```text
Loop 1 (memory-gate)
    └── Loop 2 (context) — prefetch memória
            └── Loop 6 (tool registry) — mount on-demand
Loop 3 (eval-gate) — independente; CI após Loop 1 mínimo
Loop 4 (budget-gate) — independente; integra fluxo-events
Loop 5 (governance) — independente; expande agent-policies
Loop 7 (reliability) — após Loop 2 (handoff)
Loop 8 (ontologia) — após Loop 2 (context builder)
```

**Ordem de execução:** `1 → 2 → 3` (P0) → depois `4, 5, 6, 7` em paralelo onde possível → `8` por último.

---

## 7. Evoluir em cima do existente (não reinventar)

| Kernel atual | Evolução natural |
|--------------|------------------|
| `agent-policies` | Loop 5 — novas famílias, matriz risco |
| `evidence-gate` | Loop 3 — amarrar eval-gate no close |
| `fluxo-events` | Loop 4 — eventos de budget |
| `canonical_data_check` | Loop 8 — gate ontologia/contrato DE |
| `/install-harness` | Todos — propagar novos kernels como `foundation` |

---

## 8. Top 8 evoluções (prioridade)

| # | Evolução | Loop | Anel |
|---|----------|------|------|
| 1 | `memory-gate` | 1 | Memory |
| 2 | Context Builder + handoff | 2 | Context |
| 3 | `eval-gate` + judge independente | 3 | Evaluation |
| 4 | Governance server-side + PII gate | 5 | Governance |
| 5 | `budget-gate` | 4 | Cost |
| 6 | Tool Registry | 6 | Tools |
| 7 | Checkpoints + idempotency (dev) | 7 | Reliability |
| 8 | KB/skill ontologia de negócio | 8 | Context |

---

## 9. Próximo passo imediato

1. Abrir **ADR 006** — `memory-gate` (Loop 1, Fase 0).  
2. Criar branch `feat/memory-gate` via `/nova-branch`.  
3. Executar Fases 1–4 do Loop 1 antes de iniciar Loop 2.

---

## 10. Explicitamente fora de escopo

- Monitoramento autônomo 24/7 de pipelines  
- Auto-correção operacional de jobs  
- PR automático para deploy em produção  
- Agente observador de infra em runtime  
- Dark Factory / fábrica de software autônoma  
