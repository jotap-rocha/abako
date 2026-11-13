# SPEC-012 (4/5): telas de leitura

**Status:** done  
**Blocked by:** tasks/abako/10-front-lancamento.md, tasks/abako/17-alertas.md

## What to build

Telas de leitura, só exibindo o que a API devolve (ADR 015, ADR 050): cartões e faturas (aberta ou
fechada, itens com a pessoa, crédito de estorno, limite usado), gasto real e receita do mês com
navegação entre meses, reserva (nível, falta, cobertura, aporte), sobra do R2 e alertas. O início
resume receita de caixa, gasto real, sobra, reserva e alertas (sem o vale). Termos técnicos têm
explicação em linguagem direta. Mínimo no backend: `GET /api/cartoes/{id}/faturas/{competencia}`
passa a devolver `fechamento` e `situacao` (SPEC-005-AC-11).

## Acceptance criteria

- [x] SPEC-005-AC-11: a fatura devolve o fechamento efetivo e a situação aberta ou fechada, nula sem fechamento — tested by: tests/backend/test_fatura_situacao_api.py::test_fatura_aberta_ou_fechada_pela_data
- [x] SPEC-012-AC-12: cada tela exibe os valores vindos da API sem recalcular regra, com os estados de UI tratados — tested by: frontend/src/leitura/Leitura.test.tsx::sem_regra_no_front
- [x] SPEC-012-AC-13: termos técnicos têm explicação em linguagem direta — tested by: frontend/src/leitura/Glossario.test.tsx::termos_explicados
- [x] SPEC-012-AC-14: jornada ver fatura, gasto real e alertas — tested by: tests/e2e/test_leitura.py::test_jornada_leitura

## Notes

Design provisório (mesma base visual das telas de saldo e lançamento); o usuário ajusta depois.
Os ids AC-10 e AC-11 da SPEC-012 já pertencem à idempotência no retry e à edição com versão.
