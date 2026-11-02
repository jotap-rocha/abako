# SPEC-010: recorrentes e R2

**Status:** not started  
**Blocked by:** tasks/abako/13-terceiros-repasse.md, tasks/abako/15-reserva.md

## What to build

Fixos e receitas recorrentes com ocorrência por mês, vínculo a transação, lista de vencidas não vinculadas e sobra do horizonte R2 (inicial 10 dias, configurável com vigência).

## Acceptance criteria

- [ ] SPEC-010-AC-1: o R2 conta só ocorrências não vinculadas dentro do horizonte; vencidas ficam em lista separada (INV-19) — tested by: tests/db/test_r2.py::test_f_r2_01
- [ ] SPEC-010-AC-2: a sobra do R2 exclui terceiros, a receber e crédito do vale; usa só a fatura própria (INV-18) — tested by: tests/db/test_r2.py::test_f_r2_03
- [ ] SPEC-010-AC-3: limites do horizonte são exatos (inclusão/exclusão do último dia) — tested by: tests/db/test_r2.py::test_limites_do_horizonte

## Notes

Rascunho: os critérios são formalizados em `tests/contracts/criterios.yaml` quando a SPEC for escrita.
