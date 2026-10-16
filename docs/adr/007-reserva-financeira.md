# 007 — Reserva financeira como conta dedicada com meta em meses

**Status:** Aceita
**Data:** 2026-10-16
**Autores:** time
**Reversibilidade:** difícil

---

## Contexto

A reserva estava misturada com dinheiro disponível. O usuário a mantém em uma conta de banco digital com rendimento e liquidez imediata.

## Decisão

- Reserva = **conta dedicada**.
- **Rendimento** é tipo próprio de transação (não é receita comum).
- Meta = **N meses × gasto essencial** (N inicial = 3; gasto essencial é parâmetro manual).
- Os níveis e alertas estão no ADR 023.

## Alternativas consideradas

### Opção A — Reserva como "fatia" de conta comum ❌ Rejeitada
Mistura saldo.

### Opção B — Meta fixa em reais ❌ Rejeitada
Não acompanha o custo de vida.

### Opção C — Conta dedicada + meta em meses ✅ Escolhida

## Consequências

### Positivas
- Cobertura calculável a qualquer momento.
- Saldo bruto vs. líquido conferido por snapshot.

### Negativas / Tradeoffs
- Gasto essencial é informado manualmente; categorização fica para depois.

## Fora de escopo

Detalhes de rendimento/IR da conta; categorização automática do essencial.

## Como verificar

INV-12, INV-17; fixtures F-RES-01 e F-RES-02.

## Impacto em SI/LGPD

Dado financeiro pessoal; sem impacto adicional.

## Revisão

Revisar quando a categorização do essencial for implementada.
