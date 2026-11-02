# SPEC-012 (2/5): telas de saldo e snapshot

**Status:** not started  
**Blocked by:** tasks/abako/06-front-casca.md, tasks/abako/07-saldo-snapshot.md

## What to build

Telas de saldo por conta, informar snapshot e ver divergência, com textos explicativos em linguagem direta.

## Acceptance criteria

- [ ] SPEC-012-AC-4: a tela mostra o saldo de cada conta vindo da API, sem recalcular — tested by: frontend/src/saldos/Saldos.test.tsx::mostra_saldo_da_api
- [ ] SPEC-012-AC-5: informar snapshot exibe a divergência retornada pela API — tested by: frontend/src/saldos/Snapshot.test.tsx::mostra_divergencia
- [ ] SPEC-012-AC-6: jornada login → ver saldos — tested by: tests/e2e/test_saldos.py::test_login_e_saldos

## Notes

Design ditado pelo usuário.
