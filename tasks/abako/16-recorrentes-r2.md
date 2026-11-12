# SPEC-010: recorrentes e R2

**Status:** done  
**Blocked by:** tasks/abako/15-reserva.md (a 13 e a 14 já estão entregues; a 15 é a base empilhada)
**ADR:** docs/adr/048-recorrentes-e-r2.md

## What to build

Recorrentes (fixo = despesa recorrente | receita; só em conta corrente) com ocorrência derivada por
mês, vínculo a UMA transação (evento com histórico), lista de vencidas não vinculadas e sobra do
horizonte R2 (inicial 10 dias, inclusivo, configurável com vigência). Cadastro do dia de vencimento
do cartão com vigência. Migração 0011 (SQL puro): `recorrente`, `recorrente_vinculo`,
`r2_parametro`, `cartao_vencimento`; escrita por funções `SECURITY DEFINER`; leituras `INVOKER`
(`ocorrencias_do_mes`, `r2_itens`, `r2_situacao`).

## Acceptance criteria

Fonte: `tests/contracts/criterios.yaml` (SPEC-010-AC-1..13).

- [x] SPEC-010-AC-1: só ocorrências não vinculadas de hoje a hoje + horizonte; sobra = disponível − compromissos; vencidas à parte (INV-19) — tests/db/test_r2.py::test_f_r2_01
- [x] SPEC-010-AC-2: sobra só com a fatura própria; terceiros, a receber e crédito do vale fora (INV-18) — ::test_f_r2_03
- [x] SPEC-010-AC-3: limites do horizonte exatos (hoje e hoje + horizonte entram; +1 não) — ::test_limites_do_horizonte
- [x] SPEC-010-AC-4: valor esperado até vincular; vinculada sai do R2; vínculo com histórico — test_recorrente.py
- [x] SPEC-010-AC-5: dia 29 a 31 usa o último dia válido do mês — test_recorrente.py::test_dia_29_a_31_f_r2_10
- [x] SPEC-010-AC-6: vencimento do cartão com vigência (> fechamento: mês M; senão M+1) — test_r2.py
- [x] SPEC-010-AC-7: fatura própria desconta o pago alocado (ADR 044); fatura aberta é parcial — test_r2.py
- [x] SPEC-010-AC-8: recorrente e disponível só em conta corrente — test_recorrente.py / test_r2.py
- [x] SPEC-010-AC-9: horizonte com vigência (inicial 10) — test_r2.py::test_horizonte_com_vigencia_f_r2_09
- [x] SPEC-010-AC-10: versionamento do recorrente e regras do vínculo — test_recorrente.py
- [x] SPEC-010-AC-11: isolamento por user_id (INV-13) — test_r2.py / test_recorrente.py
- [x] SPEC-010-AC-12: papéis, SECURITY DEFINER, mensagens literais, downgrade da 0011 — test_papeis.py::test_r2_papeis, test_r2_mensagens.py, test_migracao_0011.py
- [x] SPEC-010-AC-13: rotas da API rotas de recorrentes, ocorrências, vínculo, horizonte, vencimento do cartão e situação do R2 (`GET /api/r2`)

## Notes

- Fixtures F-R2-01..04 (já existiam; valores conferidos à mão: 1300.00, −500.00, 1300.00, 200.00) e
  F-R2-05..11 (novas, calculadas à mão).
- **API (feita):** rotas de recorrentes (criar, editar com `versao`, excluir),
  vincular e desvincular (`recorrente_vincular`/`recorrente_desvincular`), ocorrências do mês
  (`ocorrencias_do_mes`), horizonte (`r2_parametro_gravar`, view `r2_parametro_vigente`), vencimento
  do cartão (`vencimento_gravar`, view `vencimento_vigente`) e situação do R2 (`r2_situacao` e
  `r2_itens`, com `hoje` = data civil em `America/Sao_Paulo`, injetável). Dinheiro em texto,
  `user_id` da sessão, CSRF, AB404/AB409/AB410/AB422 -> 404/409/409/422, valores fora do log;
  regenerar o cliente OpenAPI.
- Alerta R2 e tela: task 17 (consome `alerta`, `sobra`, `vencidas` e `pendencias_vencimento`).
- **Para o front (tasks 17/18/19):** `GET /api/r2` devolve `alerta`, `sobra`, `vencidas`, `pendencias_vencimento` e `itens` (grupos receita, fixo, fatura, vencida; sem nome do recorrente: cruzar `recorrente_id` com `GET /api/recorrentes`); guardar `versao` para editar/excluir (409 AB409 = mudou desde a leitura, AB410 = nome repetido ou vínculo já usado); o horizonte e o vencimento do cartão são PUT idempotentes.
