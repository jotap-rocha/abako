# SPEC-005: faturas, parcelas e linha de crédito

**Status:** not started  
**Blocked by:** tasks/abako/09-lancamento.md

## What to build

Cartão como conta de dívida, linha de crédito compartilhada, fechamento com vigência (dia inexistente usa o último dia válido; regra do dia do fechamento), parcelas por linha, limite pelo total da compra.

## Acceptance criteria

- [ ] SPEC-005-AC-1: soma das parcelas = total e a última absorve os centavos (INV-02) — tested by: tests/db/test_parcelas.py::test_ultima_absorve_centavos
- [ ] SPEC-005-AC-2: cada parcela pertence à fatura da sua competência (INV-07) — tested by: tests/db/test_fatura.py::test_parcela_na_competencia
- [ ] SPEC-005-AC-3: limite usado soma as dívidas dos cartões da linha, com parcelas futuras e terceiros (INV-06) — tested by: tests/db/test_limite.py::test_limite_usado
- [ ] SPEC-005-AC-4: total da fatura = própria + terceiros (INV-26) — tested by: tests/db/test_fatura.py::test_total_proprio_mais_terceiros
- [ ] SPEC-005-AC-5: fechamento no dia 31 em fevereiro usa o último dia (INV-31) — tested by: tests/db/test_fechamento.py::test_dia_inexistente

## Notes

A data real de fechamento de cada cartão segue pendência externa e não bloqueia. Fixar a regra de compra no dia do fechamento (ADR 027).
