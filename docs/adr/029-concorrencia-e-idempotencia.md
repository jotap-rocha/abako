# 029 — Concorrência e idempotência como garantias de esquema

**Status:** Aceita
**Data:** 2026-10-19
**Autores:** time
**Reversibilidade:** difícil

---

## Contexto

Duplo clique, duas abas e retry após timeout podem duplicar ou sobrescrever lançamentos; duas execuções do pipeline podem corromper o analítico.

## Decisão

- Unicidade parcial: no máximo **uma versão vigente** por entidade versionada (SPEC-001).
- **Campo de versão** (controle otimista): atualização desatualizada recebe conflito (409), sem criar versão.
- **Chave de idempotência** persistida na criação; o front pode repetir a mesma chave após timeout.
- Operações sobre a **linha de crédito compartilhada** são serializadas por bloqueio transacional.
- Pipeline: `pg_advisory_lock` impede duas execuções (SPEC-014).

## Alternativas consideradas

Só trava no front ❌; deixar para cada SPEC decidir ❌ (difícil de retrofitar no esquema).

## Como verificar

INV-27, INV-28, INV-29, INV-35; testes contra Postgres real.

## Impacto em SI/LGPD

Sem impacto adicional.
