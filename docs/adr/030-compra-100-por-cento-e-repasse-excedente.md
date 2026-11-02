# 030 — Compra 100% própria ou 100% de terceiro e repasse excedente

**Status:** Aceita
**Data:** 2026-10-19
**Autores:** time
**Reversibilidade:** moderada

---

## Contexto

O ADR 009 coloca `pessoa` na transação; isso não representa divisão de uma compra entre o usuário e um familiar.

## Decisão

- v1: cada compra é **100% própria ou 100% de terceiro**; divisão é rejeitada e declarada fora de escopo.
- Repasse acima da dívida da pessoa não gera "a receber" negativo silencioso; a regra exata (rejeitar ou registrar crédito explícito) é fixada na SPEC-007.

## Alternativas consideradas

Alocações por pessoa na v1 ❌ (complexidade sem demanda).

## Como verificar

INV-10, INV-32, INV-33 (SPEC-007).

## Impacto em SI/LGPD

Descrição de terceiros é dado pessoal: fora de logs e do analítico.
