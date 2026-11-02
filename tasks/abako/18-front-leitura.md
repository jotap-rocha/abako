# SPEC-012 (4/5): telas de leitura

**Status:** not started  
**Blocked by:** tasks/abako/17-alertas.md, tasks/abako/10-front-lancamento.md

## What to build

Telas de leitura: cartões e faturas (aberta/fechada, limite usado), gasto real do mês, reserva (nível, falta, cobertura), sobra do R2 e alertas.

## Acceptance criteria

- [ ] SPEC-012-AC-10: cada tela exibe os valores vindos da API sem recalcular regra — tested by: frontend/src/leitura/Leitura.test.tsx::sem_regra_no_front
- [ ] SPEC-012-AC-11: termos técnicos têm explicação em linguagem direta — tested by: frontend/src/leitura/Glossario.test.tsx::termos_explicados
- [ ] SPEC-012-AC-12: jornada ver fatura, gasto real e alertas — tested by: tests/e2e/test_leitura.py::test_jornada_leitura

## Notes

Design ditado pelo usuário.
