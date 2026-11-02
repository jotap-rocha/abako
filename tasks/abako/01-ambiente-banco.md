# SPEC-001a: ambiente do banco e guarda de teste

**Status:** not started  
**Blocked by:** none

## What to build

Contêiner Postgres dedicado (porta 5433) com bancos `prd` e `tst`, escutando só em 127.0.0.1, Alembic em SQL puro e a guarda que faz a suíte abortar se a conexão não for a de `tst`. Versões exatas das dependências de backend fixadas.

## Acceptance criteria

- [ ] SPEC-001-AC-1: a suíte aborta se a conexão de banco não for a de `tst` — tested by: tests/db/test_guarda_tst.py::test_aborta_fora_de_tst
- [ ] SPEC-001-AC-2: o Postgres escuta só em 127.0.0.1:5433 — tested by: tests/db/test_rede.py::test_escuta_apenas_localhost
- [ ] SPEC-001-AC-3: as migrações Alembic aplicam e revertem em `tst` sem erro — tested by: tests/db/test_migracoes.py::test_aplica_e_reverte

## Notes

Migração em `prd` pede confirmação (ADR 019). Nomes de contêiner e volume via `COMPOSE_PROJECT_NAME`.
