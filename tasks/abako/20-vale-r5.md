# SPEC-013: vale e alerta R5

**Status:** not started  
**Blocked by:** tasks/abako/14-gasto-real.md, tasks/abako/19-front-formularios.md

## What to build

Página separada do vale: crédito, consumo por bolso, resta, sobra, decisão de destino e saldo total; alerta R5 quando o resta de um bolso fica negativo.

## Acceptance criteria

- [ ] SPEC-013-AC-1: pessoal = crédito − base; resta = alocação efetiva − consumo; não acumula entre meses (INV-21) — tested by: tests/db/test_vale.py::test_f_vale_01
- [ ] SPEC-013-AC-2: sobra = Σ max(resta, 0) por bolso, sem compensar estouro; a decisão nunca altera saldo (INV-25) — tested by: tests/db/test_vale.py::test_sobra_por_bolso
- [ ] SPEC-013-AC-3: saldo total do vale segue o saldo derivado normal (INV-22) — tested by: tests/db/test_vale.py::test_saldo_total
- [ ] SPEC-013-AC-4: receita total = caixa + vale e a tela principal mostra só a de caixa (INV-24) — tested by: tests/db/test_vale.py::test_receita_total
- [ ] SPEC-013-AC-5: R5 dispara quando o resta de um bolso é negativo, sem compensação — tested by: tests/backend/test_alertas.py::test_r5

## Notes

Rascunho: os critérios são formalizados em `tests/contracts/criterios.yaml` quando a SPEC for escrita.
