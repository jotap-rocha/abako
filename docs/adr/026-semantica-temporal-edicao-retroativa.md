# 026 — Semântica temporal da edição retroativa e snapshots

**Status:** Aceita
**Data:** 2026-10-19
**Autores:** time
**Reversibilidade:** difícil

---

## Contexto

A revisão adversarial externa apontou que o ADR 006 não diz o que acontece com saldos históricos e snapshots quando uma transação antiga é editada.

## Decisão

- O **snapshot é âncora observada**: nunca é recalculado nem alterado por edição de transação.
- O histórico exibido por padrão é o **corrigido hoje**: a versão vigente de cada transação.
- Cada versão guarda `recorded_at`; a consulta "o que o sistema sabia na época" existe como visão de **auditoria**.
- **Base de comparação do R4:** para cada snapshot Sk, o derivado é recalculado a partir do snapshot imediatamente anterior (ou do saldo inicial) + transações vigentes até a data de Sk. Se diferir de Sk, o R4 sinaliza; nunca corrige sozinho (complementa ADR 006).
- O saldo **atual** segue o INV-03 (último snapshot + posteriores); a edição retroativa só afeta a conferência dos snapshots anteriores.

## Alternativas consideradas

Bitemporal completo como padrão ❌ (custo alto para uso pessoal); invalidar snapshot na edição ❌ (apaga a evidência de conferência).

## Como verificar

INV-03, INV-09, INV-23, INV-30; fixture com snapshot, edição retroativa e R4 **a criar na SPEC-003** (valores calculados à mão).

## Impacto em SI/LGPD

Complementa o ADR 006.
