# SPEC-005: faturas, parcelas e linha de crédito

**Status:** done  
**Blocked by:** tasks/abako/09-lancamento.md

## What to build

Cartão como conta de dívida, linha de crédito compartilhada, fechamento com vigência (dia inexistente usa o último dia válido; regra do dia do fechamento), parcelas por linha, limite pelo total da compra.

## Acceptance criteria

- [x] SPEC-005-AC-1: soma das parcelas = total e a última absorve os centavos (INV-02) — tested by: tests/db/test_parcelas.py::test_ultima_absorve_centavos
- [x] SPEC-005-AC-2: cada parcela pertence à fatura da sua competência (INV-07) — tested by: tests/db/test_fatura.py::test_parcela_na_competencia
- [x] SPEC-005-AC-3: limite usado = total das compras com parcelas futuras menos pagamentos (INV-06) — tested by: tests/db/test_limite.py::test_limite_usado
- [x] SPEC-005-AC-4: total da fatura = soma das parcelas da competência; terceiros na SPEC-013 — tested by: tests/db/test_fatura.py::test_total_proprio_mais_terceiros
- [x] SPEC-005-AC-5: fechamento no dia 31 em fevereiro usa o último dia (INV-31) — tested by: tests/db/test_fechamento.py::test_dia_inexistente
- [x] SPEC-005-AC-6: compra no dia do fechamento entra na fatura seguinte (ADR 043) — tested by: tests/db/test_fechamento.py::test_compra_no_dia_do_fechamento
- [x] SPEC-005-AC-7: fechamento com vigência, sem recalcular compras antigas — tested by: tests/db/test_fechamento.py::test_vigencia_do_fechamento
- [x] SPEC-005-AC-8: pagamento parcial de fatura abate a dívida e não é gasto — tested by: tests/db/test_pagamento_fatura.py::test_pagamento_parcial_abate_a_divida
- [x] SPEC-005-AC-9: crédito pela API com parcelas, idempotência e versão — tested by: tests/backend/test_credito_api.py::test_credito_pela_api
- [x] SPEC-005-AC-10: editar e excluir compra parcelada — tested by: tests/db/test_parcelas.py::test_editar_e_excluir_compra_parcelada

## Notes

Decisões em `docs/adr/043-cartao-fatura-parcelas-e-limite.md`. A data real de fechamento de cada cartão segue pendência externa e não bloqueia. Terceiros e repasse ficam na SPEC-013; snapshot/R4 de fatura adiado. A migração 0006 está só no `tst`; no `prd` depende de aprovação e backup.
