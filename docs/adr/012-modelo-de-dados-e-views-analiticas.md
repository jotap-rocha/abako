# 012 — Modelo de dados e views analíticas

**Status:** Aceita
**Data:** 2026-10-16
**Autores:** time
**Reversibilidade:** difícil

---

## Contexto

Formalizar as entidades dos ADRs 006, 008, 009 e 011.

## Decisão

**Tabelas:** `pessoa`, `linha_credito`, `conta`, `categoria`, `grupo`, `estabelecimento`, `compra`, `transacao` + `transacao_versao`, `snapshot_saldo`, `parametro` (com vigência), mais as de autenticação (ADR 020: usuário/sessão) e as do ADR 023 (recorrente, ocorrência, bolso, decisão de sobra).

- Valores `NUMERIC`; JSON de valores como texto; nunca float.
- Datas = data civil `America/Sao_Paulo`.
- `user_id` em todas as tabelas.
- Views analíticas conforme o ADR 008, implementadas no **DuckDB** (o transacional é Postgres).

## Alternativas consideradas

### Opção A — Modelo "wide" por tipo ❌ Rejeitada
Difícil de evoluir.

### Opção B — Datas com timestamp/UTC ❌ Rejeitada
Erro de virada de dia.

### Opção C — Modelo normalizado, `NUMERIC`, data civil ✅ Escolhida

## Consequências

### Positivas
- Esquema estável; migrações versionadas.

## Premissas

Postgres como banco.

## Fora de escopo

Particionamento; multi-tenant por schema.

## Como verificar

INV-13, INV-14; teste de esquema (coluna `user_id`, tipos NUMERIC).

## Impacto em SI/LGPD

`user_id` em toda tabela sustenta o isolamento (INV-13).

## Revisão

Revisar se surgir multiusuário real.
