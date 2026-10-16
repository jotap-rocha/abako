# PROMPT: FLUXO_EMIT_RUNTIME

> Dev Loop — adoção prática do fluxo live: capturar `event_id` no shell + delegação do revisor

---

## Goal

Tornar **utilizável em runtime** a telemetria Opção C já implementada: o agente consegue
guardar `BUILD_ENTER_EVENT_ID` após `agent_enter` do build e emitir tasks/delegações com
`parent_event_id` correto; `revisor-codigo` documenta emit filho quando invocado durante o build.

**Fora de escopo deste loop:** hook automático Cursor `Task(...)`, backfill histórico
`silver-checklist-odcs`, ADR 005 addendum, SSE/live refresh.

---

## Quality Tier

**Tier:** production

---

## Context

- **Entregue (master):** render Opção C + tasks/delegações no SVG/resumo/timeline (PR 216748)
- **Gap atual:** `harness-build.md` pede guardar `event_id`, mas CLI só imprime
  `ok: appended …` (`config/fluxo_events/cli.py:132`); delegações ficam frágeis
- **`revisor-codigo.md`:** enter/exit simples, sem `--parent-event-id` quando filho do build
- **Honesty §1.3:** emit continua fail-soft / omitível — este loop melhora ergonomia, não
  enforcement
- **Evidência:** `EmitResult.line` já contém JSON com `event_id` (`emit.py:134`); falta expor na CLI

---

## Tasks (Prioritized)

### 🔴 RISKY (Do First)

- [x] Estender `EmitResult` (ou parser da `line`) para expor `event_id` / `run_id` tipados
- [x] Flag CLI `--print-event-id` (stdout, uma linha UUID) **ou** `--json` (linha JSON completa)
      — default inalterado (`ok: appended …`) para não quebrar scripts existentes
- [x] Testes em `tests/fluxo_events/test_emit.py` (ou novo `test_cli_emit_output.py`):
      emit com flag → stdout contém UUID válido; sem flag → comportamento legado

### 🟡 CORE

- [x] Atualizar `harness-build.md` (+ espelho `.cursor/`) com padrão shell testável, ex.:

  ```bash
  BUILD_ENTER_EVENT_ID=$(python -m config.fluxo_events emit \
    --slug {slug} --event-type agent_enter --agent harness-build --phase 3 \
    --print-event-id --no-render) || true
  ```

- [x] Wiring `revisor-codigo.md` (+ espelho): secção “delegado do build” com
  `--parent-event-id {BUILD_ENTER_EVENT_ID}` no enter/exit quando invocado durante F3
- [x] Atualizar `docs/fluxo-events-cheatsheet.md` (secção CLI) com a nova flag
- [x] Fixture de integração mínima: emit build enter → task_enter com parent → render →
      assert `exec-task` no SVG (pode estender `test_render_execution_trail.py` ou teste CLI)

### 🟢 POLISH (Do Last)

- [x] Snippet opcional em `harness-build.md`: captura + task_enter + revisor delegado (bloco copy-paste)
- [x] ADR 005: **não editar** (imutável) — se necessário, nota no cheatsheet apenas
- [x] Atualizar `HANDOFF.md` / `CONTEXT.md` se invariante CLI mudar (step SYNC do executor)

---

## Exit Criteria

- [x] `python -m pytest tests/fluxo_events/ -q` verde
- [x] `ruff check config/fluxo_events/` e `mypy config/fluxo_events/cli.py` verde
- [x] `python -m config.fluxo_events emit … --print-event-id` imprime UUID v4 em stdout (exit 0)
- [x] Sem `--print-event-id`, stdout permanece `ok: appended …` (regressão zero)
- [x] `harness-build.md` e `revisor-codigo.md` espelhados em `.cursor/agents/`
- [x] Cheatsheet documenta a flag

---

## Verify Commands

```bash
python -m pytest tests/fluxo_events/ -q
ruff check config/fluxo_events/cli.py config/fluxo_events/emit.py
python -m mypy config/fluxo_events/cli.py

# smoke manual (tmp slug):
python -m config.fluxo_events emit --slug dev-loop-fluxo-emit-runtime \
  --event-type agent_enter --agent harness-build --phase 3 \
  --print-event-id --no-render
```

---

## Progress

**Status:** COMPLETE

| Iteration | Timestamp | Task Completed | Key Decision | Files Changed |
|---|---|---|---|---|
| 1 | 2026-08-24 | CLI + wiring + tests | `--print-event-id` stdout limpo; `--json` alternativa | emit.py, cli.py, harness-build, revisor, cheatsheet, tests |

---

## Config

```yaml
mode: afk
quality_tier: production
max_iterations: 8
circuit_breaker: 3
slug: dev-loop-fluxo-emit-runtime
```

---

## Notes

- **Próximo loop (futuro):** hook Cursor `Task` / automação de subagente; dogfood
  `silver-checklist-odcs/events.jsonl`; ADR addendum Opção C via `/new-adr`
- **Não** alterar schema `fluxo-events.yaml` — só CLI + wiring + docs
- Espelhar `.claude/` ↔ `.cursor/` na mesma sessão

---

## References

- `.claude/dev/tasks/PROMPT_FLUXO_TASK_DELEGATION.md` (loop anterior — COMPLETE)
- `docs/fluxo-events-cheatsheet.md`
- `config/fluxo_events/cli.py` · `config/fluxo_events/emit.py`
- `.claude/agents/workflow/harness-build.md`
- `.claude/agents/dev/revisor-codigo.md`
- `HANDOFF.md` (pendências runtime)

---

## Como executar

```bash
/dev .claude/dev/tasks/PROMPT_FLUXO_EMIT_RUNTIME.md
```

Telemetria live (fail-soft, opcional):

```bash
/fluxo-live dev-loop-fluxo-emit-runtime
```
