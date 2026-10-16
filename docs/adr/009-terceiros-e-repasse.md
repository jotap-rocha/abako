# 009 — Uso por terceiros e repasse

**Status:** Aceita
**Data:** 2026-10-16
**Autores:** time
**Reversibilidade:** difícil

---

## Contexto

Cartões são emprestados a familiares. Quem paga de fato são os terceiros, que repassam o valor ao usuário.

## Decisão

- Atributo `pessoa` na transação (padrão herdado do cartão, sobrescrevível por transação).
- Despesa de terceiro **não é gasto real do usuário**, mas **entra** no limite usado e no total da fatura.
- **Repasse** é tipo próprio, abate o "a receber" por pessoa e não é receita.

## Alternativas consideradas

### Opção A — Ignorar terceiros ❌ Rejeitada
Fatura e limite não batem.

### Opção B — Tratar repasse como receita ❌ Rejeitada
Infla a receita.

### Opção C — `pessoa` por transação + repasse como tipo ✅ Escolhida

## Consequências

### Positivas
- Visão "a receber por pessoa"; fatura exibida como própria + terceiros.

## Premissas

Terceiros não têm login.

## Fora de escopo

Cobrança automática; multiusuário real.

## Como verificar

INV-10, INV-11, INV-26; fixture F-FAT-01.

## Impacto em SI/LGPD

Nomes de terceiros são dados pessoais: nunca em logs; exibir conforme `rules/seguranca.md`.

## Revisão

Revisar se terceiros passarem a ter acesso ao sistema.
