# ADR 004 — Kernel evidence-gate (collect/check + foundation)

- **Status:** Aceita
- **Data:** 2026-08-13
- **Decisores:** mantenedores do Agent Harness Canônico
- **Contexto:** ship `evidencias-testes-obrigatorios` (PRD `02-prd.md`, harness `03-harness.md`)

## Contexto

“Done” e critérios de aceite dependiam de claims em prosa (DoD, test-first narrado,
`revisor-codigo`, campos de `entregas.jsonl`). `/validar` é suite global; Stop IDE é
parcial. Faltava um kernel que tornasse aceite **auditável por artefato**.

## Decisão

1. Kernel **separado** `evidence-gate` (`evidence-gate.yaml` + `config/evidence_gate/` +
   CLI `collect|check`) — **não** fundir com `/validar`, `agent-policies` ou DE.
2. Install **foundation always-on** (contrato + engine via `config/` + seed
   `.harness/evidence-gate/` KEEP).
3. `collect` **executa** o comando; cap **2 MiB** com **fail-on-exceed**; alvo **2×** sem
   hard timeout no yaml; prova atual **LWW** + `audit.jsonl` append-only.
4. `evidencias_ref` obrigatório em `metrics/entregas.jsonl`.
5. Sem skill MUST no MVP (cheatsheet + wiring agents); sem agent “evidence officer”;
   sem Stop dual.

## Consequências

- harness-build/ship e DoD bloqueiam sem check verde + ref.
- Filhos herdam o freio sem categoria opt-in.
- Honesty §1.3: gate local ≠ impossibilidade de manifesto forjado.
- Cross-link: Bash deny ≠ aceite; `/validar` permanece.

## Impacto em SI/LGPD

SI **a** — sem PII/secrets em evidências; fixtures só paths/exit/logs sintéticos.
