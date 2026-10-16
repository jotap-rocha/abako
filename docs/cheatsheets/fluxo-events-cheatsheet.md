# fluxo-events — cheatsheet (1 página)

Kernel de **telemetria live** do fluxo SDD (mapa 0–4) **e** do Dev Loop (mapa 0–6,
slug `dev-loop-{nome}`). Ortogonal a `/validar`, **evidence-gate** (aceite hard) e
**agent-policies** (Bash deny). STATUS.md / scorecard / PROGRESS / entregas permanecem —
live é complementar (**não unifica** com evidence-gate).

## CLI

```bash
python -m config.fluxo_events check
python -m config.fluxo_events emit --slug {slug} --event-type agent_enter --agent <nome> --phase 0-4
python -m config.fluxo_events emit --slug {slug} ... --run-id {uuid} --parent-event-id {uuid}
python -m config.fluxo_events emit --slug {slug} --event-type agent_enter --agent harness-build --phase 3 \
  --print-event-id --no-render   # stdout: só event_id (BUILD_ENTER_EVENT_ID=$(…))
python -m config.fluxo_events emit ... --json                     # stdout: linha JSONL completa
python -m config.fluxo_events emit --slug dev-loop-{nome} --event-type agent_enter --agent dev-loop-executor --phase 0-6
python -m config.fluxo_events emit ... --no-render          # opt-out auto-render
python -m config.fluxo_events render --slug {slug}
python -m config.fluxo_events truncate --slug {slug} --keep 100
```

Helper: `slug_from_prompt_path("PROMPT_FOO.md")` → `dev-loop-foo`.

Paths: `.claude/projetos/{slug}/fluxo/events.jsonl` + `live.html` (+ espelho `.cursor/`).
Stack local (não versionada): `projetos/{slug}/fluxo/stack.json` — gitignored; fail-soft.
Dev Loop: `.claude/projetos/dev-loop-{nome}/fluxo/`.

## Dual-map

| Prefixo do slug | Mapa | Fases |
|---|---|---|
| (qualquer, sem `dev-loop-`) | `sdd_map` | 0–4 |
| `dev-loop-*` | `dev_loop_map` | 0–6 (LOAD…SYNC) |

Agents Dev: `prompt-crafter`, `dev-loop-executor`. Wiring: `/dev`, `DEV-LOOP.md`.
**`--dry-run` não emite.** `EXIT_COMPLETE` → truncate `--keep 100` + re-render.

## Live Opção C (previsto + execução real)

O `live.html` (layout Opção C):

1. **Mapa previsto** — `build_flow_svg` esmaecido (`fluxograma-previsto`): todos os agentes
   possíveis por fase SDD/Dev.
2. **Execução real** — `build_execution_trail_svg`: agentes usados + setas temporais;
   **tasks** (`task_enter`/`task_exit` com `task_id`) e **subagentes delegados**
   (`agent_enter` filho via `parent_event_id`) aparecem **sob** o agente orquestrador.
3. **Resumo** — checklist aninhada (agente → task N / → subagente).
4. **Atividade** — timeline humana (sem `agent_enter` cru).

Wiring build: `harness-build.md` — emit `task_enter`/`task_exit` por task + `agent_enter`/`exit`
do subagente com `--parent-event-id` do enter do build. **Sem emit = não aparece** (fail-soft).

`build_causal_svg` permanece no engine (testes); não é o painel principal do live.

Campos aditivos (`version: 1`): `event_id`, `run_id`, `parent_event_id` (UUID v4).
Parent: **explícito** > topo de `stack.json` > omitido (órfão). SVG puro (sem JS/CDN).

## Caps / concorrência

- Cap **2 MiB** → rotate **keep-tail** + warning soft (≠ evidence-gate fail-on-exceed)
- Append **sem lock** / stack **sem mutex** (G2-a) best-effort
- Truncate default **N=100** + re-render + evento `ship_truncate`
- Fail-soft: emit/render/truncate/stack **nunca** bloqueiam SDD nem `/dev`

## SI

Só metadados (`event_type`, `ts`, `phase`, `agent`, `task_id`, `slug`, `source`,
`event_id`, `run_id`, `parent_event_id`).
Proibido: prompt, diff, PII, secret, connection string.

## Naming PT-BR (obrigatório)

Orthografia do pacote: **fluxo** (com **x**). Nunca **flujo** (com **j**) em paths/código/docs
do pacote. Guardrail: `tests/fluxo_events/test_naming_ptbr.py` (escopo = pacote, não repo).
Sem agent “fluxo officer”.

## Ortogonalidade (não unificar)

- **Telemetria ≠ aceite** (evidence-gate)
- **Telemetria ≠ Bash deny** (agent-policies)
- **`/validar` permanece** (ruff+mypy+pytest); testes em `tests/fluxo_events/`
- STATUS / scorecard / PROGRESS **não** substituídos

## Honesty §1.3

Telemetria **local**. Emit omitível; eventos forjáveis; HTML pode ficar stale; stack
não persiste cross-machine. Sem Edit policies / branch protection nenhum freio impede de fato.

Ver: `docs/adr/005-kernel-fluxo-events.md` (+ addenda Dev Loop / visual / causal) · seed
`.harness/fluxo-events/` · `/fluxo-live`.
