# SPEC-006: estorno

**Status:** not started  
**Blocked by:** tasks/abako/11-faturas-parcelas.md

## What to build

Estorno integral e com parcelas pagas, devolução de limite, crédito na próxima fatura aberta e líquido zero.

## Acceptance criteria

- [ ] SPEC-006-AC-1: estorno integral devolve o limite total e não movimenta conta corrente (INV-08) — tested by: tests/db/test_estorno.py::test_f_est_01
- [ ] SPEC-006-AC-2: estorno com parcelas pagas devolve o limite das não pagas e gera crédito na próxima fatura aberta (INV-08) — tested by: tests/db/test_estorno.py::test_f_est_02
- [ ] SPEC-006-AC-3: o líquido da compra estornada é zero — tested by: tests/db/test_estorno.py::test_liquido_zero

## Notes

Rascunho: os critérios são formalizados em `tests/contracts/criterios.yaml` quando a SPEC for escrita.
