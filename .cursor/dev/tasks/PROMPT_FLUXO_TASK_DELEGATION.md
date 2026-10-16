# PROMPT: FLUXO_TASK_DELEGATION

> Dev Loop — telemetria de tasks e subagentes no live Opção C

---

## Goal

Tasks (`task_enter`/`task_exit`) e subagentes delegados (`agent_enter` com `parent_event_id`)
aparecem no `live.html` sob cada gate; wiring documentado em `harness-build`.

---

## Quality Tier

**Tier:** production

---

## Context

- Kernel: `config/fluxo_events/` · render Opção C já entrega previsto + execução real
- Gap: build não emitia `task_enter`; render ignorava delegações
- ADR: `docs/adr/005-kernel-fluxo-events.md` (addendum delegação = wiring, não schema novo)
- Honesty §1.3: ainda fail-soft / omitível — sem hook automático Cursor Task

---

## Tasks (Prioritized)

### 🔴 RISKY (Do First)

- [x] Helpers `delegated_children` / `task_enter_completed` em `render.py`

### 🟡 CORE

- [x] SVG execução: pills `task NN` e `→ subagente` sob agente pai
- [x] Resumo aninhado + timeline com prefixo `↳`
- [x] Wiring `harness-build.md` (task_enter/exit + subagente delegado)
- [x] Testes `test_render_execution_trail.py` (+ delegação)

### 🟢 POLISH (Do Last)

- [x] Atualizar `docs/fluxo-events-cheatsheet.md` (secção delegação)
- [x] PROMPT Dev Loop (este arquivo)

---

## Exit Criteria

- [x] `python -m pytest tests/fluxo_events/ -q` verde
- [x] `ruff check config/fluxo_events/render.py` verde
- [x] `build_execution_trail_svg` contém `exec-task` quando há `task_enter` no fixture
- [x] `harness-build.md` documenta emit por task e subagente

---

## Progress

**Status:** COMPLETE

| Iteration | Timestamp | Task Completed | Key Decision | Files Changed |
|---|---|---|---|---|
| 1 | 2026-08-19 | render + wiring + tests | parent_event_id liga task/subagente ao enter do build | render.py, harness-build, tests, cheatsheet |

---

## Config

```yaml
mode: afk
quality_tier: production
max_iterations: 10
circuit_breaker: 3
```

---

## Notes

Próximo SDD build deve emitir `task_enter`/`task_exit` por task; re-render do slug atualiza
live. Backfill de `silver-checklist-odcs/events.jsonl` é opcional (dogfood histórico).

---

## References

- `.claude/design/features/fluxo-live-execucao-ux-mockups.html`
- `docs/fluxo-events-cheatsheet.md`
