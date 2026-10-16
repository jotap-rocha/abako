---
domain: postgres-financeiro
topic: quick-reference
---

# Postgres financeiro — Quick Reference

| Assunto | Regra |
|---|---|
| Tipo de valor | `NUMERIC` com escala da SPEC-001. JSON de valores como texto. |
| Saldo derivado | Último snapshot + transações válidas posteriores (versão vigente, não excluídas). |
| Edição | Nova versão em `transacao_versao`; nunca update in place. |
| Exclusão | Lógica. |
| Transferência | Duas pernas, soma zero. |
| Parcela | Uma linha por parcela; última absorve centavos; soma = total. |
| Limite usado | Soma das dívidas dos cartões da linha (parcelas futuras e terceiros incluídos). |
| Data de negócio | Data civil `America/Sao_Paulo`. |
| `user_id` | Em toda tabela; filtro pelo `user_id` da sessão. |
| Papel da aplicação | Sem `UPDATE/DELETE` nas tabelas de versão. |
| Papel do pipeline | Somente leitura no Postgres; escreve só no arquivo DuckDB analítico. |
| Banco de teste | `tst` vazio e descartável; suíte aborta se a conexão não for `tst`. |

## Views analíticas (no DuckDB)

`saldo_diario`, `gasto_mensal`, `fatura_resumo`, `limite_linha`, `a_receber_por_pessoa`, `cobertura_reserva`.
