---
domain: postgres-financeiro
topic: ledger-dinheiro
confidence: null
mcp_validated: null
---

# abako — ledger e dinheiro

Fonte: `tests/contracts/invariantes.yaml`, `fixtures/numericos.yaml`, ADRs 006, 011, 012, 013, 023.

## Fluxo
1. Ache a invariante (INV-xx) e a fixture (F-xxx) da regra. Se não existir, crie as duas **antes** do código.
2. Escreva o teste com o valor esperado **da fixture** (calculado à mão), nunca recalculado pela fórmula do código.
3. Implemente a regra no SQL (view/função em `db/`); o backend só chama.

## Regras de dinheiro
- `NUMERIC(p,s)` com escala da SPEC-001; `Decimal` no Python; **texto** no JSON. Nunca `float`.
- Parcelas: `total / n` arredondado para baixo no centavo; **a última absorve o resto** (F-PARC-01: 100,00/3 → 33,33 · 33,33 · 33,34).
- Arredondar uma vez, no fim; não encadear arredondamentos.
- Soma das parcelas == total, sempre (propriedade para Hypothesis).

## Ledger
- Edição = nova linha em `transacao_versao`; só a vigente conta; exclusão lógica. Nunca `UPDATE/DELETE` pelo papel `app`.
- Saldo derivado = último snapshot + transações válidas posteriores. Divergência só **sinalizada** (R4).
- Transferência = 2 pernas, soma zero, não é gasto.
- Estorno: sem parcela paga → limite integral, fatura reduz, nada na conta corrente; com parcela paga → limite das não pagas, crédito do pago na próxima fatura aberta, líquido zero.

## Propriedades Hypothesis sugeridas
soma das parcelas == total · transferência soma zero · saldo derivado independe da ordem de lançamento · editar N vezes preserva N+1 versões e só a última conta.
