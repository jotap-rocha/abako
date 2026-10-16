---
name: to-tasks
description: Break a plan, spec, or PRD into local task files (tasks/{slug}/*.md) using tracer-bullet vertical slices. Use when user wants to convert a plan into local markdown tasks, work offline without GitHub, or implement step-by-step without a remote issue tracker.
---

# To Tasks

Break a plan into independently-implementable local task files using vertical slices (tracer bullets).

Task files live under `tasks/{slug}/` at the project root — `{slug}` is the **same**
as `.claude/projetos/{slug}/` (not a flat dump in `tasks/`). No GitHub required —
everything stays local.

## Process

### 1. Gather context

Work from whatever is already in the conversation context. If the user passes a file path as an argument (e.g. `PRD.md`), read it. Otherwise look for `PRD.md` at the project root or ask the user to point to the source document.

### 2. Explore the codebase (optional)

If you have not already explored the codebase, do so to understand the current state. Task titles and descriptions should use the project's domain glossary and respect ADRs in the area being touched.

### 3. Draft vertical slices

Break the plan into **tracer bullet** tasks. Each task is a thin vertical slice that cuts through ALL integration layers end-to-end, NOT a horizontal slice of one layer.

<vertical-slice-rules>
- Each slice delivers a narrow but COMPLETE path through every layer (schema, API, UI, tests)
- A completed slice is demoable or verifiable on its own
- Prefer many thin slices over few thick ones
</vertical-slice-rules>

### 4. Quiz the user

Present the proposed breakdown as a numbered list. For each slice, show:

- **Title**: short descriptive name
- **Blocked by**: which other slices (if any) must complete first

Ask the user:

- Does the granularity feel right? (too coarse / too fine)
- Are the dependency relationships correct?
- Should any slices be merged or split further?

Iterate until the user approves the breakdown.

### 5. Write local task files

For each approved slice, create a file under `tasks/{slug}/` (create the folder if
needed). Use this naming convention:

```
tasks/{slug}/01-short-title.md
tasks/{slug}/02-short-title.md
tasks/{slug}/03-short-title.md
```

Numbers are zero-padded to two digits and reflect the **global** implementation order
across the canônico (blockers first). Title is kebab-case, max 5 words.

**Blocked by** must use the full repo-relative path (same slug or cross-slug if ever
needed), e.g. `tasks/{slug}/01-short-title.md` — not a bare filename.

Use the template below for each file:

<task-template>
# [Task title]

**Status:** not started  
**Blocked by:** [tasks/{slug}/NN-title.md, or "none"]

## What to build

A concise description of this vertical slice. Describe the end-to-end behavior, not layer-by-layer implementation.

Avoid specific file paths or code snippets — they go stale fast.

## Acceptance criteria

For each criterion, state how it will be proven with a test (unit, integration, or e2e — name
the seam / path). Paths must be compatible with the evidence-gate manifesto
(`test_paths` + `command` em `evidencias/tasks/<id>.yaml`). If a criterion genuinely has no
test (e.g. pure config/docs change), write "no test — <reason>" **and** plan a human waiver
marker (`waiver: { human: true, reason: "..." }`) — silent omission is not allowed.

- [ ] Criterion 1 — tested by: path/to/test.py::test_name
- [ ] Criterion 2 — tested by: ...
- [ ] Criterion 3 — tested by: ... (or: no test — <reason> + waiver humano)

## Notes

Any decisions, constraints, or context the implementer needs to know. Leave blank if none.
</task-template>

### 6. Create / update tasks/README.md

After writing all task files, create (or update) `tasks/README.md` with:

- Index table of **slug folders** → issue ranges
- Per-pacote table: number, title, status, blocked-by
- One-line description of the overall goal for the active slug

This file is the dashboard — update it as tasks move from "not started" → "in progress" → "done".
Also update `.claude/projetos/{slug}/04-tasks-index.md` paths to `tasks/{slug}/NN-…`.

## Implementing tasks

When the user says "implement task X" or "start task 03":

1. Resolve path `tasks/{slug}/NN-*.md` (slug from active projeto / STATUS / pergunta)
2. Read the task file
3. Check that all blockers are marked "done" in their files
4. For each acceptance criterion with a "tested by" note, write that test first — it should
   fail (the code it exercises doesn't exist yet). Skip only criteria explicitly marked
   "no test — <reason>".
5. Implement the vertical slice until the tests from step 4 pass
6. Run `/validar` (gate ruff + mypy + pytest)
7. Update the task file: change `Status:` to `done` and tick all acceptance criteria
8. Update `tasks/README.md` status table (and `04-tasks-index.md` if present)
9. Commit all changes with message `feat(task-NN): <title>` — only after gate is green
10. Append one line to `metrics/entregas.jsonl` (create the file if it doesn't exist) **with
   `evidencias_ref`** pointing to the task manifesto after `collect`→`check` verde.

The delivery record must follow the schema in `metrics/README.md`. Use the task number as `"issue"`. Example:

```json
{"issue": 1, "titulo": "esqueleto andante", "data": "2026-06-27", "criterios_aceite": {"total": 3, "atendidos": 3}, "gate": {"resultado": "verde", "tentativas_ate_verde": 1}, "revisor": {"veredito": "aprovado", "bloqueantes": 0, "ressalvas": 0}, "intervencoes_humanas": 0, "commit": "<short-sha>", "evidencias_ref": ".claude/projetos/{slug}/evidencias/tasks/1.yaml"}
```

Get the commit SHA with `git rev-parse --short HEAD` (step 7 já criou o commit). This record is what feeds `/scorecard` — without it the delivery is invisible to reporting. Evidence-gate is hard; `/validar` remains the global suite.

## Telemetria live (fluxo-events) — fail-soft

No enter/exit desta fase/agent, emita metadados (nunca bloqueia SDD):

```bash
python -m config.fluxo_events emit --slug {slug} --event-type agent_enter --agent <este-agent> --phase <0-4> || true
# ao sair:
python -m config.fluxo_events emit --slug {slug} --event-type agent_exit --agent <este-agent> --phase <0-4> || true
```

Fail-soft: erro de emit/render → warning stderr; continue o fluxo. Só metadados (sem prompt/PII/secret).
Live em `projetos/{slug}/fluxo/live.html` é **complementar** a STATUS.md / scorecard / evidence-gate — não os substitui.

