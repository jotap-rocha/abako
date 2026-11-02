# SPEC-003: saldo derivado e snapshot

**Status:** not started  
**Blocked by:** tasks/abako/05-login.md

## What to build

Saldo derivado por conta (último snapshot + transações válidas posteriores), snapshot de saldo, divergência R4, saldo de qualquer dia passado, regra de edição retroativa do ADR 026.

## Acceptance criteria

- [ ] SPEC-003-AC-1: saldo derivado = último snapshot + transações vigentes posteriores (INV-03) — tested by: tests/db/test_saldo.py::test_saldo_derivado_f_saldo_01
- [ ] SPEC-003-AC-2: o R4 lista exatamente as contas em que derivado ≠ snapshot (INV-23) — tested by: tests/db/test_r4.py::test_r4_lista_divergencias
- [ ] SPEC-003-AC-3: edição retroativa não altera o snapshot e o R4 sinaliza a divergência (INV-30) — tested by: tests/db/test_retroativa.py::test_edicao_retroativa_sinaliza_r4
- [ ] SPEC-003-AC-4: saldo de um dia passado é consultável — tested by: tests/db/test_saldo.py::test_saldo_em_data_passada

## Notes

Criar a fixture F-SALDO-03 (edição retroativa) com valores calculados à mão.
