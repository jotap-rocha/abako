# SPEC-008: gasto real

**Status:** not started  
**Blocked by:** tasks/abako/12-estorno.md, tasks/abako/13-terceiros-repasse.md

## What to build

Gasto real do mês, excluindo transferência, investimento, repasse, rendimento, pagamento de fatura, terceiros e conta de benefício.

## Acceptance criteria

- [ ] SPEC-008-AC-1: gasto real exclui as categorias não-gasto (INV-04) — tested by: tests/db/test_gasto_real.py::test_f_gasto_01
- [ ] SPEC-008-AC-2: pagamento de fatura nunca é gasto; o gasto é contado nas parcelas do mês da fatura (INV-05) — tested by: tests/db/test_gasto_real.py::test_pagamento_fatura_nao_e_gasto
- [ ] SPEC-008-AC-3: despesa de terceiro não é gasto real mas entra no limite (INV-11) — tested by: tests/db/test_gasto_real.py::test_terceiro_fora_do_gasto
- [ ] SPEC-008-AC-4: despesa e receita de conta de benefício ficam fora do gasto e da receita de caixa (INV-20) — tested by: tests/db/test_gasto_real.py::test_conta_de_beneficio

## Notes

Rascunho: os critérios são formalizados em `tests/contracts/criterios.yaml` quando a SPEC for escrita.
