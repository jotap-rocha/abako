# SPEC-013: vale e alerta R5

**Status:** done  
**Blocked by:** tasks/abako/14-gasto-real.md (receita total e gasto real), tasks/abako/17-alertas.md (função `alertas`, ADR 049), tasks/abako/19-front-formularios.md (formulário de lançamento, que ganha o bolso)

## What to build

Página separada do vale (VR): crédito, consumo por bolso, resta, sobra, decisão de destino e saldo
total; alerta R5 quando o resta de um bolso do mês corrente fica negativo. O VA é outra conta de
benefício, sem bolsos, que aparece na página de benefícios (receita e saldo) e entra na receita
total. A tela principal nunca mostra o vale. Decisões e modelagem: ADR 052.

## Acceptance criteria

Fonte da verdade: `tests/contracts/criterios.yaml` (SPEC-013-AC-1 a AC-20). Resumo:

- [x] SPEC-013-AC-1: pessoal = crédito − base; resta = alocação efetiva − consumo; não acumula entre meses (INV-21) — `tests/db/test_vale.py::test_f_vale_01`, `::test_f_vale_07_encadeamento`
- [x] SPEC-013-AC-2: sobra = Σ max(resta, 0) por bolso, sem compensar; a decisão nunca altera saldo (INV-25) — `tests/db/test_vale.py::test_f_vale_03_estouro_nao_compensado`, `tests/db/test_vale_propriedades.py`
- [x] SPEC-013-AC-3: saldo total do vale = saldo derivado normal (INV-22) — `tests/db/test_vale.py::test_f_vale_05_saldo_total`
- [x] SPEC-013-AC-4: receita total = caixa + benefício (VR e VA); a de caixa é a da tela principal (INV-24) — `tests/db/test_vale.py::test_f_vale_09_receita_total_com_va`
- [x] SPEC-013-AC-5: R5 por bolso com resta < 0, só no mês corrente, sem compensação — `tests/db/test_vale_alertas.py`
- [x] SPEC-013-AC-6: marcação da conta VR (benefício do usuário, vigência por mês)
- [x] SPEC-013-AC-7: VA sem bolsos, fora do gasto real, na página de benefícios
- [x] SPEC-013-AC-8: decisão com histórico, só em mês encerrado, nova versão substitui
- [x] SPEC-013-AC-9: base de trabalho com vigência; crédito menor que a base; mês sem crédito
- [x] SPEC-013-AC-10: bolso obrigatório na despesa do VR, opcional em conta de benefício sem VR marcado (classificar antes), proibido nos demais casos
- [x] SPEC-013-AC-11: isolamento por `user_id`
- [x] SPEC-013-AC-12: papéis, mensagens literais, downgrade seguro (migração 0013)
- [x] SPEC-013-AC-13: API (situação do mês, decisão, parâmetro, benefícios; `GET /api/alertas` com R5; lançamento com bolso) — `tests/backend/test_vale_api.py` e `tests/backend/test_alertas.py::test_r5`
- [x] SPEC-013-AC-14: página do vale e tela principal sem vale; escolha de bolso no formulário — `frontend/src/vale/Vale.test.tsx::mostra_o_que_a_api_devolveu_sem_recalcular`, `tests/e2e/test_vale.py::test_marcar_vr_lancar_com_bolso_e_ver_a_pagina_do_vale`
- [x] SPEC-013-AC-15: estados da página do vale (sem_conta, sem_credito, carregando, erro, 401, mês) — `frontend/src/vale/Vale.test.tsx::sem_conta_leva_a_marcar_o_vr`
- [x] SPEC-013-AC-16: decisão da sobra só com `mes_encerrado`, histórico e erros 422/409 — `frontend/src/vale/Vale.test.tsx::desabilitada_com_mes_encerrado_falso`
- [x] SPEC-013-AC-17: bolso no formulário (só despesa no VR), na edição, na chave de idempotência e na lista — `frontend/src/vale/Bolso.test.tsx::bolso_obrigatorio_no_vr_e_ausente_fora_dele`
- [x] SPEC-013-AC-18: VA sem bolsos e VR marcado na lista de benefícios — `frontend/src/vale/Vale.test.tsx::va_sem_bolsos_e_vr_com_a_marca`
- [x] SPEC-013-AC-19: R5 na tela de alertas (forte, sem dispensar) e fora do Início — `frontend/src/vale/Vale.test.tsx::inicio_nao_consulta_nem_mostra_o_vale`
- [x] SPEC-013-AC-20: glossário do vale — `frontend/src/vale/Vale.test.tsx::explica_vale_bolso_resta_sobra_e_estouro`

## Notes

Banco, API e front entregues: ADR 052 e 053, fixtures F-VALE-06 a F-VALE-12, migração 0013
(`db/migrations/versions/0013_vale.py`; no `prd` só após backup e aval do dono), rotas `/api/vale/*`,
página `/vale` e campo Bolso no lançamento. O Início nunca mostra o vale.
