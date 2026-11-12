# SPEC-007: terceiros e repasse

**Status:** done  
**Blocked by:** tasks/abako/12-estorno.md

## What to build

Despesa de terceiro (compra 100% de terceiro no cartão), repasse e saldo a receber por pessoa, com a regra do repasse maior que a dívida. Convenções no ADR 045 (Aceita).

## Acceptance criteria

Os testes de cada critério estão em `tests/contracts/criterios.yaml` (campo `teste`).

- [x] SPEC-007-AC-1: a receber por pessoa = max(D − R, 0), com D = total das compras de terceiro (parcelas futuras) e R = repasses (INV-10, F-FAT-01, F-REP-03)
- [x] SPEC-007-AC-2: compra dividida entre próprio e terceiro, ou pessoa fora do cartão, é recusada pelo banco (INV-32, F-REP-04)
- [x] SPEC-007-AC-3: repasse acima da dívida é aceito e vira crédito da pessoa; a receber nunca é negativo (INV-33, F-REP-01)
- [x] SPEC-007-AC-4: fatura total = própria + terceiros e limite usado com terceiros (INV-26, INV-06, F-FAT-01, F-LIM-01, F-REP-03)
- [x] SPEC-007-AC-5: estorno de compra de terceiro reduz a dívida da pessoa pelo T inteiro (F-REP-02)
- [x] SPEC-007-AC-6: isolamento por user_id, inclusive leituras com o id de outro usuário (INV-13)
- [x] SPEC-007-AC-7: o nome da pessoa não vai a mensagem de erro nem ao papel do pipeline
- [x] SPEC-007-AC-8: repasse é tipo próprio, só em conta corrente, não é receita nem compra
- [x] SPEC-007-AC-9: cadastro de pessoa versionado, com exclusão lógica
- [x] SPEC-007-AC-10: papéis (`app` sem UPDATE/DELETE, `pipeline` só leitura) e downgrade seguro da 0008
- [x] SPEC-007-AC-11: API: recusa de divisão no corpo, rotas de pessoa, repasse, a receber e fatura com própria/terceiros

## Notes

Fixar a regra do repasse excedente (feito): aceitar e mostrar `credito_da_pessoa` (ADR 045 itens 4 e 5).

- **Para o fin-backend:** `lancamento_gravar` ganhou o 15º parâmetro `p_pessoa` (DEFAULT NULL); `pessoa_gravar`/`pessoa_excluir` (id da pessoa devolvido, nome só na tabela `pessoa`); leituras `a_receber_pessoas(user, pessoa?)`, `fatura_resumo` (total, própria, terceiros) e `fatura_itens` com `pessoa_id` no fim. O nome nunca em log, URL ou erro.
- **Para a SPEC-008 (gasto real):** ler `parcela_ativa` e filtrar `pessoa_id IS NULL` (terceiros fora); `repasse` já é tipo à parte.
- **Para a task 19 (front):** tela e formulário de pessoa; seletor de pessoa (`pessoa_id`) na compra a crédito e no repasse; lista de a receber com `credito_da_pessoa`; fatura com "própria / terceiros" e pessoa nos itens (valor negativo possível na competência do crédito de estorno); tratar 404, 409 e 422 pelo `X-Abako-Erro`.
