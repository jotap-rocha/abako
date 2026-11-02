# SPEC-007: terceiros e repasse

**Status:** not started  
**Blocked by:** tasks/abako/11-faturas-parcelas.md

## What to build

Despesa de terceiro (compra 100% de terceiro), repasse e saldo a receber por pessoa, com regra para repasse maior que a dívida.

## Acceptance criteria

- [ ] SPEC-007-AC-1: a receber por pessoa = despesas de terceiros − repasses (INV-10) — tested by: tests/db/test_terceiros.py::test_a_receber
- [ ] SPEC-007-AC-2: compra dividida entre próprio e terceiro é rejeitada (INV-32) — tested by: tests/backend/test_terceiros.py::test_divisao_rejeitada
- [ ] SPEC-007-AC-3: repasse acima da dívida segue a regra fixada, sem a receber negativo silencioso (INV-33) — tested by: tests/db/test_terceiros.py::test_repasse_excedente

## Notes

Fixar aqui a regra exata do repasse excedente (rejeitar ou registrar crédito explícito).
