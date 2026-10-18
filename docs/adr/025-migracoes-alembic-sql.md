# 025 — Migrações do Postgres com Alembic em SQL puro

**Status:** Aceita
**Data:** 2026-10-17
**Autores:** time
**Reversibilidade:** fácil

---

## Contexto

O transacional é Postgres em contêiner dedicado e o analítico é DuckDB gerado pelo pipeline. Só o Postgres precisa de migrações versionadas e reversíveis. As regras vivem em views/funções SQL, não em modelos ORM.

## Decisão

- **Alembic** como runner de versões, com migrações escritas à mão em SQL (`op.execute`), **sem autogenerate**, em `db/migrations/`.
- Cada migração tem `upgrade` e `downgrade`; alvo por `ABAKO_ENV` (padrão `tst`); `prd` só com confirmação e backup recente.
- O DuckDB **não** usa migrações: o arquivo é reconstruído pelo pipeline a cada execução.

## Alternativas consideradas

### Opção A — SQL numerado + script próprio ❌ Rejeitada
Reinventa versionamento e reversão.

### Opção B — Alembic com autogenerate ❌ Rejeitada
Exige modelos ORM; as regras estão no SQL.

### Opção C — Alembic em SQL puro ✅ Escolhida

## Consequências

### Positivas
- Versionamento e reversão prontos; encaixa na KB `postgres-financeiro` (migracoes).

### Negativas / Tradeoffs
- Dependência Python extra; SQL escrito à mão exige disciplina de teste.

## Impacto em SI/LGPD

Migração em `prd` passa pelo crivo do usuário (ADR 019/024).

## Revisão

Revisar se o esquema ganhar modelos ORM.
