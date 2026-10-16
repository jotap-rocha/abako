# Seed `fluxo-events` (KEEP no re-install)

Destino no filho: `.harness/fluxo-events/`

## Layout operacional por projeto

```text
.claude/projetos/{slug}/fluxo/
├── events.jsonl   # append via `python -m config.fluxo_events emit`
└── live.html      # regenerado via `render` (LWW)
```

Dev Loop: slug sintético `dev-loop-{nome}` (helper `slug_from_prompt_path`).

Este seed traz stubs + SCHEMA. O runtime escreve sob `projetos/{slug}/fluxo/`.
Contrato raiz: `fluxo-events.yaml` (`sdd_map` 0–4 + `dev_loop_map` 0–6).

## Invariantes

- Só metadados (agent, phase, task_id, timestamps, event_type)
- Fail-soft: nunca bloqueia SDD nem `/dev`
- Cap 2 MiB com rotate keep-tail (soft warning)
- Truncate: `truncate --keep 100` + re-render
- Ortogonal a evidence-gate e agent-policies
- Orthografia PT-BR: **fluxo** (x), nunca **flujo** (j)
