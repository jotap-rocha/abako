# SPEC-009: reserva e cobertura

**Status:** not started  
**Blocked by:** tasks/abako/09-lancamento.md

## What to build

Reserva como conta dedicada com meta em meses de gasto essencial, níveis, falta, cobertura em meses e aporte mensal até a data-alvo.

## Acceptance criteria

- [ ] SPEC-009-AC-1: cobertura = saldo da reserva ÷ gasto essencial (INV-12) — tested by: tests/db/test_reserva.py::test_cobertura
- [ ] SPEC-009-AC-2: níveis mudam exatamente em 50% e 100% da meta (INV-17) — tested by: tests/db/test_reserva.py::test_cortes_nivel
- [ ] SPEC-009-AC-3: aporte mensal necessário até a data-alvo — tested by: tests/db/test_reserva.py::test_aporte_mensal
- [ ] SPEC-009-AC-4: a reserva exibe líquido, imposto acumulado e bruto = líquido + imposto; a cobertura usa o líquido (INV-37) — tested by: tests/db/test_reserva.py::test_bruto_liquido_f_res_03

## Notes

Bruto e líquido decididos no ADR 034 (criar F-RES-03 à mão). O gasto essencial é parâmetro manual (ADR 007).
