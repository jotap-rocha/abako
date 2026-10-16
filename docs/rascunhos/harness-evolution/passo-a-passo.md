# Passo a passo prático — melhorias do harness (Cursor, sem API-KEY)

> Complemento ao deck `harness-evolution-tecnico` e ao `plan.md`.  
> Foco: **o que fazer hoje** vs **o que automatizar depois** (Loops SDD).

---

## Orchestration — ✅ FORTE

| Passo | Ação prática |
|-------|----------------|
| 1 | Ao iniciar build, abrir `/fluxo-live` ou `projetos/{slug}/fluxo/live.html` |
| 2 | Por task, emitir `task_enter` / `task_exit` (comandos em `harness-build.md`) |
| 3 | No close: `/validar` → `revisor-codigo` → `python -m config.evidence_gate check` |
| 4 | Criar `docs/sdd-transitions.md` — fases 0–4 e quem controla cada transição |
| 5 | Cursor: modelo rápido no `/dev`; modelo forte só em `harness-design` e revisor |

**Depois (Loop SDD):** state machine explícita + review paralelo automatizado.

---

## Context — ⚠️ PARCIAL

| Passo | Ação prática |
|-------|----------------|
| 1 | Ao terminar cada fase SDD, criar `HANDOFF.md` em `.claude/projetos/{slug}/` |
| 2 | Abrir **nova sessão** Cursor; colar só HANDOFF + task atual |
| 3 | No prompt, citar só KBs necessários (`@kb/databricks`) — não domínio inteiro |
| 4 | Manter `CLAUDE.md` e rules estáveis; volátil vai para `STATUS.md` ou task |
| 5 | **Futuro Loop 2:** template HANDOFF + skill `context-handoff` |

**Template HANDOFF mínimo:**

```markdown
# HANDOFF — {fase} — {data}
## Decisões tomadas
## Pendências
## Arquivos alterados
## Próximo passo
```

---

## Memory — ❌ FRACO

| Passo | Ação prática |
|-------|----------------|
| 1 | Criar `.harness/memory/MEMORY.md` (projeto filho ou canônico dogfood) |
| 2 | Seções: `## Decisões` \| `## Erros a não repetir` \| `## Convenções` |
| 3 | Ao `harness-ship`: adicionar 3 bullets (o que funcionou / falhou) |
| 4 | Ao abrir `harness-build`: ler `MEMORY.md` + `STATUS.md` antes de codar |
| 5 | **Futuro Loop 1:** ADR 006 + `config/memory_gate/` + hook automático |

---

## Tools — ⚠️ PARCIAL

| Passo | Ação prática |
|-------|----------------|
| 1 | Revisar `.mcp.json` — só MCPs da task atual |
| 2 | Antes de shell arriscado: `python -m config.agent_policies check "comando"` |
| 3 | Se `deny`/`ask`: parar e pedir humano (sem `HARNESS_ALLOW_DESTRUCTIVE`) |
| 4 | Scripts: exit 0=ok, 1=retryable, 2=fatal |
| 5 | Documentar tools permitidos por task em `harness-build.md` |

**Futuro Loop 6:** `config/tool_registry/` + MCP on-demand.

---

## Reliability — ⚠️ PARCIAL

| Passo | Ação prática |
|-------|----------------|
| 1 | Antes de `rm`/deploy/push: commit parcial + anotar no HANDOFF |
| 2 | Dev Loop: salvar em `.claude/dev/progress/` ao pausar |
| 3 | Se `/validar` falhar 3x na mesma task → parar; registrar em MEMORY.md |
| 4 | Nunca repetir push/deploy sem `git log` / status pipeline |
| 5 | **Futuro Loop 7:** idempotency + circuit breaker no kernel |

---

## Evaluation — ⚠️ PARCIAL

| Passo | Ação prática |
|-------|----------------|
| 1 | Close task: `python -m config.evidence_gate collect` + `check` |
| 2 | `/validar` até verde; anotar `tentativas_ate_verde` em `entregas.jsonl` |
| 3 | **Novo chat** Cursor; colar diff + critérios de aceite |
| 4 | Pedir veredito: aprovado \| ressalvas \| bloqueado |
| 5 | **Futuro Loop 3:** `tests/eval_golden/` + CI no `make test` |

---

## Cost — ❌ AUSENTE (Cursor assinatura)

> **Não calcule $ por token.** Use limites e eficiência.

| Passo | Ação prática |
|-------|----------------|
| 1 | Limite manual: max **15 interações** agente por task |
| 2 | Sessão > **90 min** → HANDOFF e encerrar |
| 3 | Cursor Settings → modelo **rápido** default; forte só design/review |
| 4 | `entregas.jsonl`: `tentativas_ate_verde` + `intervencoes_humanas` |
| 5 | Planilha: `R$ assinatura ÷ tasks fechadas/mês` |
| 6 | **Futuro Loop 4:** `budget-gate.yaml` com `max_turns` e `max_minutes` |

---

## Governance — ⚠️ PARCIAL

| Passo | Ação prática |
|-------|----------------|
| 1 | Sempre `/nova-branch` antes de `harness-build` |
| 2 | Branch protection Azure: `main` só via PR |
| 3 | Antes de commit grande: `agent_policies check` nos comandos |
| 4 | Nunca PII/senha/token no chat (env / Key Vault) |
| 5 | Deploy prod: PR + aprovação humana |
| 6 | **Futuro Loop 5:** matriz propose/apply + skill PII scan |

---

## Comece esta semana (3 ações)

1. **MEMORY.md + HANDOFF** entre fases  
2. **Close de task:** `/validar` → revisor em chat novo → evidence-gate  
3. **`/nova-branch`** + branch protection + `agent_policies check`
