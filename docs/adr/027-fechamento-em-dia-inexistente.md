# 027 — Fechamento do cartão em dia inexistente e compra no dia do fechamento

**Status:** Aceita
**Data:** 2026-10-19
**Autores:** time
**Reversibilidade:** moderada

---

## Contexto

O fechamento cadastrado pode cair em dia que não existe no mês (31 em fevereiro). A data real de cada cartão ainda é pendência externa (ADR 013).

## Decisão

- Dia de fechamento inexistente no mês usa o **último dia válido** do mês.
- A regra para compra feita **no próprio dia** do fechamento (entra na fatura que fecha ou na seguinte) é fixada na SPEC-005, com fixture, e vale por vigência do cadastro.
- Datas reais seguem editáveis com vigência e calibradas por snapshot de fatura (ADR 013); a pendência não bloqueia SPEC.

## Alternativas consideradas

Rejeitar cadastro de dia 29-31 ❌ (cartões reais fecham nesses dias).

## Como verificar

INV-31; fixtures de fevereiro e de compra no dia do fechamento (SPEC-005).

## Impacto em SI/LGPD

Complementa o ADR 013.
