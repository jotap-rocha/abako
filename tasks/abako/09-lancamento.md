# SPEC-004: lançamento por tipo e edição versionada

**Status:** done  
**Blocked by:** tasks/abako/07-saldo-snapshot.md

## What to build

Lançamento manual por tipo (débito/pix, receita, transferência, investimento, rendimento com bruto e imposto retido), edição que cria nova versão, exclusão lógica, idempotência de criação e conflito em atualização desatualizada. Tipos de conta (corrente, reserva, investimento, benefício), com a caixinha/cofre como reserva que pertence a um banco, e edição de conta. Decisões no ADR 042.

## Acceptance criteria

- [x] SPEC-004-AC-1: transferência tem duas pernas e soma zero; perna solta é barrada pelo esquema (INV-01) — tested by: tests/db/test_transferencia.py::test_duas_pernas_soma_zero (+ test_perna_solta_e_barrada_pelo_esquema)
- [x] SPEC-004-AC-2: editar cria nova versão, preserva histórico e só a vigente conta (INV-09) — tested by: tests/db/test_versionamento.py::test_edicao_cria_versao (+ test_editar_transferencia_versiona_as_duas_pernas)
- [x] SPEC-004-AC-3: repetir a criação com a mesma chave não duplica, inclusive em paralelo (INV-28) — tested by: tests/backend/test_idempotencia.py::test_mesma_chave_nao_duplica (+ tests/db/test_lancamento_regras.py::test_mesma_chave_em_paralelo_devolve_o_primeiro)
- [x] SPEC-004-AC-4: atualização com versão desatualizada retorna conflito 409, também em edição simultânea de lançamento ou conta (INV-29) — tested by: tests/backend/test_conflito.py::test_versao_desatualizada (+ test_duas_edicoes_simultaneas_so_uma_passa, test_duas_edicoes_de_conta_simultaneas)
- [x] SPEC-004-AC-5: exclusão é lógica e a transação deixa de contar — tested by: tests/db/test_exclusao.py::test_exclusao_logica (+ test_excluido_nao_volta_nem_e_editado)
- [x] SPEC-004-AC-6: rendimento registra bruto e imposto; o creditado na conta é bruto − imposto (INV-36) — tested by: tests/db/test_rendimento.py::test_liquido_creditado
- [x] SPEC-004-AC-7: a caixinha vira reserva que pertence ao banco, por edição versionada — tested by: tests/db/test_conta_versao.py::test_caixinha_pertence_ao_banco_e_edicao_cria_versao (+ frontend/src/saldos/EditarConta.test.tsx::marca_a_caixinha_como_reserva_do_banco)
- [x] SPEC-004-AC-8: a mesma chave com outros dados é recusada (422) — tested by: tests/backend/test_idempotencia.py::test_mesma_chave_com_outros_dados_e_recusada
- [x] SPEC-004-AC-9: crédito, repasse, data futura, valor não positivo e transferência inválida são recusados (422) — tested by: tests/db/test_lancamento_regras.py e tests/backend/test_lancamentos_api.py::test_regras_viram_422_com_mensagem
- [x] SPEC-004-AC-10: a aplicação só escreve pelas funções do banco, com o usuário da sessão — tested by: tests/db/test_papeis.py::test_app_sem_update_delete (+ test_escrita_so_pelas_funcoes, tests/backend/test_lancamentos_api.py::test_isolamento_e_csrf)

## Notes

Decisões do usuário em 2026-11-09 (ADR 042):

- **Crédito e repasse** existem na lista de tipos, mas são recusados até a SPEC-005 (cartão, fatura, parcelas) e a SPEC-007 (pessoa, repasse). Por isso a SPEC-004 entrega cinco dos sete tipos.
- **"O imposto não é gasto real"** saiu do INV-36 e foi para o INV-04: só dá para testar quando existir o gasto real (SPEC-008). A fixture F-REND-01 já traz o `gasto_real: "0.00"` esperado.
- **Data futura** é recusada; previsão de gastos entra pelos recorrentes (SPEC-010).
- **Chave repetida com outros dados** é erro (422), não devolve o original.
- **Caixinha/cofre:** conta do tipo reserva com nome livre, que pertence a uma conta corrente do mesmo banco (`conta_mae_id`), com saldo próprio. Guardar nela é transferência.
- Transferência com conta de benefício fica para a SPEC-013 (vale).
- A 0005 é irreversível com dados (o downgrade se recusa); no `prd`, só com backup e aval.

Revisões: `revisor-codigo` reprovou na 1ª passada (downgrade que apagaria dado; critério de gasto real sem teste) e aprovou com ressalvas no reteste; `fin-seguranca` aprovou com ressalvas. Achados aplicados.
