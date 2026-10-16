# sisfin

## Ideia

Sistema financeiro pessoal. O usuário quer ter o controle das próprias finanças: saber quanto tem nos bancos, quanto está gastando e quanto do orçamento mensal está apertado ou folgado. Funciona com frontend, backend e automações por trás. O nome `sisfin` é provisório.

## SI Assessment

Nível: **c** — PII / dados financeiros pessoais. Também **d** na prática: o desenvolvimento usa o banco com dados reais (ADR 014, risco assumido pelo usuário).

Implicações:
- `[AVISO_LGPD]` declarado no `CLAUDE.md`.
- `prd` somente leitura para agentes; escrita só em `tst`.
- Deny/ask/hooks conforme o ADR 019.
- Sem credencial bancária armazenada ou solicitada (ADR 010).
- Segredos só por `.env` + gitleaks (ADR 018).

## Tipo de Projeto

**a** — Aplicação / API, com um pipeline de dados local pequeno (transacional → analítico, ADR 008).
Stack prevista: React + TypeScript (PWA) · FastAPI · PostgreSQL (`prd`/`tst`) + DuckDB (analítico, arquivo separado) · pipeline Python.

O pipeline é um componente do MVP, mas o projeto não é de pipeline puro: os gates de Medallion/Databricks não se aplicam (não há camadas bronze/silver/gold nem Spark).

## Próximos passos

1. Concluir o `/grill-me` (lacunas em `01-grill.md`).
2. `harness-define` → `harness-design` (PRD já rascunhado em `02-prd.md`).
3. `/to-tasks` para transformar as SPEC-001..013 em tasks.
