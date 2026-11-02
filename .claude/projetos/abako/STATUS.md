# abako
Slug: abako
Iniciado em: 2026-10-16

## SI Assessment: Nível c

## Tipo: a — Aplicação / API (com pipeline local pequeno)

## Git
- Branch atual (edições ainda sem commit): `chore/ci-minimo`; commitar os docs do SDD em branch própria (ex.: `chore/sdd-abako`), não na do CI
- Tronco: nunca commitar SDD direto no master/main

## Fase atual: 3 — Harness montado e conferido contra o disco (2026-10-19), pronto para tasks (`/to-tasks`, offline; sem issue tracker externo)

## Histórico de mudanças

- 2026-10-18: decisões D1..D8 da revisão adversarial externa aprovadas pelo usuário (D2 parcialmente: regra aprovada, data real de fechamento dos cartões segue pendência externa). Fase afetada: grill/PRD. Cascata: `01-grill.md` (D1..D8 aprovadas, [confirmar] de concorrência/idempotência/trava/ciclo de vida resolvidos), `02-prd.md` (SPECs renumeradas 001..014, stories 6/10/12/24 ajustadas e 27..29 novas, Out of Scope ampliado, migração de INV-xx por SPEC). Feito em 2026-10-19: `invariantes.yaml` (INV-27..35, specs), `CLAUDE.md`, `03-harness.md`, ADRs 026–032, correções de fin-seguranca/revisor-codigo. Pendente: `criterios.yaml` (vazio até cada SPEC), fixtures novas (SPEC-003, 005). Ainda sem tasks, então sem cascata em `tasks/`.

- 2026-10-19: harness-design. PRD finalizado; `03-harness.md` revisado (deriva em backup-restore, ledger-dinheiro, pipeline, pwa corrigida; espelhos `.cursor/` sincronizados). Nada commitado.

## Checklist
- [x] 0. Ideia + SI assessment (2026-10-16)
- [x] 1. Grill concluído (2026-10-16) — decisões 006–023; lacunas restantes são só pendências externas em `01-grill.md`
- [x] 1b. harness-define: pipeline 10 perguntas + lentes implícitas + critérios de sucesso (2026-10-18); adversarial-judge NÃO rodado (pendente decisão do usuário)
- [x] 1c. Revisão adversarial externa: D1..D8 aprovadas (2026-10-18)
- [x] 2. PRD gerado (2026-10-19) — `02-prd.md`, SPECs 001..014, com SI Considerations; só local
- [x] 3. Harness montado (2026-10-19) — revisão contra o disco em `03-harness.md` (deriva corrigida, sem scaffold novo); adversarial-judge não usado por decisão do usuário
- [x] 4. Tasks criadas (rascunho, 21 tasks em `tasks/abako/`, aguardando validação do usuário) — 2026-10-19; frontend fino antecipado (ADR 033)
- [ ] 5. Implementação concluída
- [ ] 6. Ship / retrospectiva
