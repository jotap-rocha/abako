# 011 — Tipos de transação, parcelas e limite

**Status:** Aceita
**Data:** 2026-10-16
**Autores:** time
**Reversibilidade:** difícil

---

## Contexto

É preciso distinguir gasto real de movimentação de dinheiro.

## Decisão

**Sete tipos:** débito/pix, crédito, receita, transferência (2 pernas, soma zero), investimento (transferência para conta tipo investimento), repasse de terceiro, rendimento.

**Matriz de campos por tipo:** data, tipo, categoria dependente do tipo, estabelecimento, grupo dentro de categoria, valor, descrição curta, conta, pessoa. Receita indica a conta de destino.

**Parcelas:**
- Uma linha por parcela, ligada à competência da fatura.
- A **compra** guarda a data original.
- A última parcela absorve os centavos.
- O gasto real conta **por parcela, no mês da fatura**.
- O **limite é consumido pelo valor total da compra**: limite usado = soma das dívidas dos cartões da linha, incluindo parcelas futuras e terceiros.

## Alternativas consideradas

### Opção A — Uma linha por compra ❌ Rejeitada
Não permite gasto por mês.

### Opção B — Limite só pela parcela do mês ❌ Rejeitada
Subestima o limite usado.

### Opção C — Uma linha por parcela + limite pelo total ✅ Escolhida

## Consequências

### Positivas
- Regras precisas e testáveis; formulário dinâmico por tipo.

## Premissas

A semântica de limite dos cartões do usuário confere (verificação pendente).

## Fora de escopo

Juros de parcelamento; câmbio.

## Como verificar

INV-01, 02, 04, 05, 06, 11; fixtures de parcelamento (centavos).

## Impacto em SI/LGPD

Dado financeiro pessoal; sem impacto adicional.

## Revisão

Revisar após confirmar a semântica de limite dos cartões.
