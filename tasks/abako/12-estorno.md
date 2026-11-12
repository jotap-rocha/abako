# SPEC-006: estorno

**Status:** done  
**Blocked by:** tasks/abako/11-faturas-parcelas.md

## What to build

Estorno integral e com parcelas pagas, devolução de limite, crédito na próxima fatura aberta e líquido zero.

## Acceptance criteria

Os testes de cada critério estão em `tests/contracts/criterios.yaml` (campo `teste`).

- [x] SPEC-006-AC-1: estorno integral devolve o limite total e não movimenta conta corrente (INV-08, F-EST-01)
- [x] SPEC-006-AC-2: estorno com parcelas pagas devolve o limite das não pagas e gera crédito na próxima fatura aberta (INV-08, F-EST-02)
- [x] SPEC-006-AC-3: o líquido da compra estornada é zero
- [x] SPEC-006-AC-4: parcela paga em parte gera crédito só da parte paga (F-EST-03)
- [x] SPEC-006-AC-5: alocação do pago entre compras por competência, data e parcela; crédito sai do pool (F-EST-04)
- [x] SPEC-006-AC-6: estorno no dia do fechamento cai na fatura seguinte
- [x] SPEC-006-AC-7: pagamento maior que a dívida (F-EST-05)
- [x] SPEC-006-AC-8: edição ou exclusão de compra com alguma parte paga é recusada (F-EST-06)
- [x] SPEC-006-AC-9: compra original preservada, um estorno por compra, gasto real nas competências originais
- [x] SPEC-006-AC-10: depois de um estorno, nenhum lançamento já gravado do cartão é editado ou excluído
- [x] SPEC-006-AC-11: faturas de competência anterior à do crédito não mudam

## Notes

Convenções no ADR 044 (Aceita). Juros e encargos ficam para depois (ADR 044 item 11).

- **Para a SPEC-008 (gasto real):** ler a view `parcela_ativa`, e não `transacao_vigente`, para o
  gasto sair das competências originais da compra estornada; o crédito P não é receita nem
  redutor extra de gasto (ADR 044 item 5).
- **Para a SPEC-012 (telas):** a fatura devolve o crédito P como item negativo `parcela 1/1` com o
  `transacao_id` do estorno; a tela deve rotulá-lo como "crédito de estorno", não como parcela.
  O formulário de estorno usa `POST /api/lancamentos/{id}/estorno` (task 19).
