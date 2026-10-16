# 015 — Stack: React + TypeScript, FastAPI, pipeline Python

**Status:** Aceita
**Data:** 2026-10-16
**Autores:** time
**Reversibilidade:** difícil

---

## Contexto

Uso em PC e celular; o usuário é forte em Python/SQL e fraco em web.

## Decisão

- **React + TypeScript** como PWA (Vite provável).
- **FastAPI**, com cliente TS gerado do OpenAPI.
- **Pipeline em Python.**
- **PostgreSQL** para o transacional e **DuckDB** para o analítico (ADR 008).
- Regras financeiras como **views/funções SQL**.

## Alternativas consideradas

### Opção A — App nativo ❌ Rejeitada
Custo.

### Opção B — Backend Node ❌ Rejeitada
Perde o Python do usuário.

### Opção C — SQLite no lugar do Postgres ❌ Rejeitada
Sem tipo decimal, sem papéis (não impõe a imutabilidade do ledger do ADR 019), sem funções armazenadas e sem tipo de data.

### Opção D — React PWA + FastAPI + Postgres/DuckDB + SQL ✅ Escolhida

## Consequências

### Positivas
- Contrato tipado front/back; regra de dinheiro testável em SQL.

## Premissas

Android 11 suporta PWA; versões exatas fixadas na SPEC-001.

## Fora de escopo

App nativo; SSR.

## Como verificar

OpenAPI versionado; cliente TS gerado em CI; nenhuma regra financeira duplicada no front.

## Impacto em SI/LGPD

Sem segredo no bundle; ver `rules/frontend.md` e `rules/seguranca.md`.

## Revisão

Revisar se o PWA não atender aos requisitos de uso no celular.
