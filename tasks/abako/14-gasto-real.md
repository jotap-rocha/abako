# SPEC-008: gasto real

**Status:** done
**Blocked by:** tasks/abako/12-estorno.md, tasks/abako/13-terceiros-repasse.md
**ADR:** docs/adr/046-gasto-real-e-receita-de-caixa.md

## What to build

Gasto real do mês, excluindo transferência, investimento, repasse, rendimento (e o imposto dele),
pagamento de fatura, terceiros e conta de benefício; mais a receita de caixa e a receita total do
mês. Débito conta pela data civil do lançamento; crédito, por parcela na competência da fatura
(`parcela_ativa`, que já tira a compra estornada em todas as competências originais). Débito em
reserva ou investimento conta como gasto. Mês é parâmetro (`AAAA-MM`); o padrão "mês corrente" é
da API. Migração 0009: só funções INVOKER (`gasto_real`, `gasto_real_itens`, `gasto_real_por_conta`,
`receita_caixa`, `receita_beneficio`, `receita_total`, `mes_inicio`).

## Acceptance criteria

Fonte: `tests/contracts/criterios.yaml` (SPEC-008-AC-1..10).

- [x] SPEC-008-AC-1: gasto real exclui as categorias não-gasto (INV-04) — tests/db/test_gasto_real.py::test_f_gasto_01
- [x] SPEC-008-AC-2: pagamento de fatura nunca é gasto; o gasto é contado nas parcelas do mês da fatura (INV-05) — ::test_pagamento_fatura_nao_e_gasto
- [x] SPEC-008-AC-3: despesa de terceiro não é gasto real mas entra no limite (INV-11) — ::test_terceiro_fora_do_gasto
- [x] SPEC-008-AC-4: despesa e receita de conta de benefício ficam fora do gasto e da receita de caixa (INV-20) — ::test_conta_de_beneficio
- [x] SPEC-008-AC-5: estorno tira a compra do gasto nas competências originais; o crédito não é receita (ADR 044 item 5) — ::test_estorno_nas_competencias_originais_f_gasto_03
- [x] SPEC-008-AC-6: receita de caixa exclui repasse, rendimento e benefício; total = caixa + benefício (INV-24) — ::test_receita_de_caixa_f_gasto_02
- [x] SPEC-008-AC-7: mês misto, débito em reserva/investimento conta, soma do ano só de saídas próprias — ::test_mes_misto_f_gasto_02
- [x] SPEC-008-AC-8: isolamento por user_id (INV-13) — ::test_leituras_com_user_id_de_outro_usuario_devolvem_zero
- [x] SPEC-008-AC-9: papéis, leitura pura, mês inválido recusado, mensagens literais, downgrade da 0009
- [x] SPEC-008-AC-10: rotas `GET /api/gasto-real` e `GET /api/receita` (user_id da sessão, dinheiro em texto, 422 no mês inválido)

## Notes

- **Para a task 18 (front):** chamar `gasto-real` e `receita` com `mes` opcional; resolver o nome da
  conta de `por_conta` por `conta_id` (a API não devolve nome); tratar 422/AB422 e 401. Não há
  gasto por categoria (o modelo não tem categoria).
- **Para a SPEC-014:** o pipeline não executa estas funções; lê `transacao_vigente` e
  `parcela_ativa` e não leva `descricao` ao DuckDB (ADR 045).
