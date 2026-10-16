# ADR 005 — Kernel fluxo-events (telemetria live SDD)

- **Status:** Aceita
- **Data:** 2026-08-13
- **Decisores:** mantenedores do Agent Harness Canônico
- **Contexto:** ship `visao-grafica-fluxo-agentes` (PRD `02-prd.md`, harness `03-harness.md`)

## Contexto

O fluxo SDD 0–4 (brainstorm→ship) só era observável via chat/STATUS. Faltava um painel
live estrutural (todas as fases/agents) com highlight do ativo, sem acoplar a SSE nem
substituir DoD/evidence-gate/scorecard.

## Decisão

1. Kernel **separado** `fluxo-events` (`fluxo-events.yaml` + `config/fluxo_events/` + CLI
   `emit|render|truncate`) — **não** fundir com evidence-gate, agent-policies ou `/validar`.
2. Install **foundation always-on** (contrato + engine via `config/` + seed
   `.harness/fluxo-events/` KEEP).
3. Live **sem SSE**: híbrido emit→render HTML; `http.server` opcional.
4. Cap **2 MiB** com **rotate keep-tail** + warning soft (não fail-on-exceed).
5. Ship: truncate últimos **N=100** + re-render + `ship_truncate`.
6. Fail-soft em emit/render/truncate — nunca bloqueia SDD.
7. Sem agent “fluxo officer”; wiring enter/exit nos agents/skills SDD existentes.
8. Sem skill MUST no MVP (cheatsheet + `/fluxo-live`).

## Consequências

- Agents SDD ganham one-liner de telemetria; omissão não falha DoD.
- Filhos herdam o painel via foundation sem categoria opt-in.
- Honesty §1.3: telemetria local ≠ fidelidade perfeita.
- Cross-link: telemetria ≠ aceite ≠ Bash deny; STATUS/scorecard intactos.

## Impacto em SI/LGPD

SI **a** — só metadados de processo; sem PII/prompts/secrets no event log.

---

## Addendum — Dev Loop live (2026-08-17)

Ship `fluxo-events-dev-loop-live`.

### Decisão adicional

1. Contrato ganha `dev_loop_map` (fases 0–6: LOAD→VALIDATE→INIT_PICK→EXECUTE_VERIFY→
   UPDATE_CHECK→LOOP_LOG→SYNC; agents `prompt-crafter`, `dev-loop-executor`).
2. `render` bifurca por prefixo: slug `dev-loop-*` → `dev_loop_map`; senão → `sdd_map`.
3. Helper `slug_from_prompt_path(PROMPT_*.md)` → `dev-loop-{nome}` (kebab/`[a-z0-9-]`).
4. Wiring + aviso UX em crafter, executor, `/dev`, `DEV-LOOP.md`; **`--dry-run` não emite**.
5. `EXIT_COMPLETE` → emit exit + `truncate --keep 100` + re-render (fail-soft).
6. Guardrail PT-BR: paths do pacote usam **fluxo** (x); pytest rejeita **flujo** (j).
7. Caps 2 MiB / truncate N=100 / sem SLA / event_types existentes **preservados**.
8. Continua **ortogonal** a evidence-gate (aceite) e agent-policies (Bash deny).

### Honesty §1.3

Inalterado: telemetria local/forjável; omitir emit não quebra DoD do Dev Loop.

---

## Addendum — Fluxograma visual (grafo de agentes) (2026-08-18)

Ship `fluxo-grafo-visual-agentes`.

### Contexto

O `live.html` renderizava apenas **cartões** de fase (lista), não o fluxograma que o nome
"Visão gráfica do fluxo" promete. Faltava representação de nós/arestas.

### Decisão adicional

1. `render.build_flow_svg` (função pura) gera um **fluxograma SVG**: nós de fase encadeados
   por setas (marker `arrowhead`) + nós de agente por fase.
2. Estados visuais derivam do mesmo `ActiveState`: fase `< ativa` = `done`; fase ativa =
   `active`; agente ativo destacado. Sem novo evento nem campo no schema.
3. SVG **inline** (sem JS, sem CDN) — abre offline; `viewBox` + `width=100%` responsivo.
4. Layout **determinístico** (geometria fixa) → testável (`tests/fluxo_events/test_render_graph.py`).
5. Painel de fases + timeline **preservados** (compat com testes/aceite anteriores);
   o grafo é um bloco adicional no topo.
6. Dual-map inalterado: grafo usa `dev_loop_map` (0–6) para slug `dev-loop-*`, senão `sdd_map`.

### Fora deste ship

- Grafo **causal real** de delegações (exigiria `run_id` / `parent_event_id` no schema) —
  hoje o grafo mostra o fluxo **canônico previsto**, não a árvore de chamadas executadas.
- SSE / animação client-side; Canvas.

---

## Addendum — Grafo causal real (2026-08-18)

Ship `fluxo-grafo-causal`.

### Contexto

O SVG canônico (`build_flow_svg`) mostra o mapa **previsto**. Faltavam identidade de
evento e aresta causal para desenhar a árvore real de execução no mesmo `live.html`.

### Decisão adicional

1. Schema **aditivo** (`version: 1` mantida): `event_id`, `run_id`, `parent_event_id`
   (UUID v4). Emits novos geram `event_id`/`run_id` se omitidos; override explícito ok.
   Load/render aceitam eventos legados sem os campos (órfãos ok; sem backfill).
2. Parent: valor **explícito** = fonte de verdade; senão topo de
   `projetos/{slug}/fluxo/stack.json` (gitignore; fail-soft; **sem mutex**).
3. `render.build_causal_svg` (puro) + segundo SVG no `live.html`
   (`data-testid="fluxograma-causal"`). Nós: `phase_enter` (raiz) + `agent_enter` +
   `task_enter`. Exits / `ship_truncate` permanecem só na timeline.
4. CLI: `--run-id` / `--parent-event-id`. Wiring SDD + Dev Loop (+ espelho `.cursor/`).
5. Labels de UUID truncados visualmente (8 chars + …) — SHOULD de legibilidade.
6. Caps 2 MiB / truncate N=100 / dual-map / fail-soft / ortogonalidade **preservados**.
7. Sem agent “fluxo officer”; sem fork do kernel; sem SSE/Canvas; sem toggle JS.

### Honesty §1.3

Inalterado: telemetria local/forjável; omissão de emit/stack não bloqueia SDD nem `/dev`.
