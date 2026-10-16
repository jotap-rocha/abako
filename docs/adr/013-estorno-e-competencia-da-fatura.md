# 013 — Estorno e competência da fatura

**Status:** Aceita
**Data:** 2026-10-16
**Autores:** time
**Reversibilidade:** difícil

---

## Contexto

Estornos têm duas situações distintas, e a data de fechamento dos cartões é incerta no início.

## Decisão

- **Nenhuma parcela paga** → estorno integral: o limite é devolvido por inteiro, a fatura é reduzida e **nenhum dinheiro** vai à conta corrente.
- **Alguma parcela paga** → o limite devolve a soma das **não pagas**; o valor das pagas vira **crédito na próxima fatura aberta**; o líquido da compra é zero.
- **Editar compra:** avisar e recalcular só as parcelas não pagas.
- **Fechamento** cadastrado por cartão com vigência; a competência é editável manualmente; o snapshot de fatura calibra.

## Alternativas consideradas

### Opção A — Estorno sempre em dinheiro na conta ❌ Rejeitada
Contradiz o comportamento do cartão.

### Opção B — Recalcular parcelas pagas ❌ Rejeitada
Reescreve o passado.

### Opção C — Regras integral vs. com parcelas pagas ✅ Escolhida

## Consequências

### Positivas
- Regras de borda explícitas; erros iniciais de fechamento corrigíveis por edição.

## Premissas

O usuário aceita errar um pouco no início até calibrar o fechamento.

## Fora de escopo

Chargeback/disputa; estorno parcial por item.

## Como verificar

INV-07, INV-08; fixtures F-EST-01 e F-EST-02.

## Impacto em SI/LGPD

Dado financeiro pessoal; sem impacto adicional.

## Revisão

Revisar após confirmar as datas de fechamento reais.
