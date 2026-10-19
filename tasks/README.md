# Tasks

| Slug | Tasks | Objetivo |
|---|---|---|
| [abako](abako/) | 01–21 | Sistema financeiro pessoal local-first (ledger, saldos, gasto real, reserva, cartões, vale) |

## abako

| # | Task | Status | Bloqueada por |
|---|---|---|---|
| 01 | [SPEC-001a: ambiente do banco e guarda de teste](01-ambiente-banco.md) | done | — |
| 02 | [SPEC-001b: check, rastreabilidade e CI](02-check-rastreabilidade.md) | not started | 01 |
| 03 | [SPEC-001c: esquema base e garantias](03-esquema-base.md) | not started | 02 |
| 04 | [SPEC-001d: backup e restauração](04-backup-restore.md) | not started | 03 |
| 05 | [SPEC-002: login e sessão](05-login.md) | not started | 03 |
| 06 | [SPEC-012 (1/5): casca do frontend e login](06-front-casca.md) | not started | 05 |
| 07 | [SPEC-003: saldo derivado e snapshot](07-saldo-snapshot.md) | not started | 05 |
| 08 | [SPEC-012 (2/5): telas de saldo e snapshot](08-front-saldos.md) | not started | 06, 07 |
| 09 | [SPEC-004: lançamento por tipo e edição versionada](09-lancamento.md) | not started | 07 |
| 10 | [SPEC-012 (3/5): formulário de lançamento](10-front-lancamento.md) | not started | 08, 09 |
| 11 | [SPEC-005: faturas, parcelas e linha de crédito](11-faturas-parcelas.md) | not started | 09 |
| 12 | [SPEC-006: estorno](12-estorno.md) | not started | 11 |
| 13 | [SPEC-007: terceiros e repasse](13-terceiros-repasse.md) | not started | 11 |
| 14 | [SPEC-008: gasto real](14-gasto-real.md) | not started | 12, 13 |
| 15 | [SPEC-009: reserva e cobertura](15-reserva.md) | not started | 09 |
| 16 | [SPEC-010: recorrentes e R2](16-recorrentes-r2.md) | not started | 13, 15 |
| 17 | [SPEC-011: alertas R1, R2 e R4](17-alertas.md) | not started | 07, 15, 16 |
| 18 | [SPEC-012 (4/5): telas de leitura](18-front-leitura.md) | not started | 17, 10 |
| 19 | [SPEC-012 (5/5): formulários restantes](19-front-formularios.md) | not started | 18 |
| 20 | [SPEC-013: vale e alerta R5](20-vale-r5.md) | not started | 14, 19 |
| 21 | [SPEC-014: pipeline e analítico](21-pipeline-analitico.md) | not started | 20 |

A SPEC-012 (frontend) é entregue em 5 incrementos (tasks 06, 08, 10, 18 e 19); o frontend fino começa logo após o login. Os critérios são rascunho e viram `SPEC-NNN-AC-N` em `tests/contracts/criterios.yaml` quando cada SPEC for escrita.

> Nota: a linha da task 01 do abako usa `issue: 1`, que coincide com uma linha herdada do harness canônico (decisão do usuário em 2026-10-19: manter assim; o `check` pega a última linha com o número).
