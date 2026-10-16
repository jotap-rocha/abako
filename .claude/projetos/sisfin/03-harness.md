# sisfin — Harness

> Decisões de harness do projeto (ADR 016, 019). Estado: plano; o `harness-architect` ainda não rodou.

## Já criado

| Artefato | Caminho |
|---|---|
| Agente | `.claude/agents/fin/fin-frontend.md` |
| KB | `.claude/kb/react-pwa/`, `.claude/kb/postgres-financeiro/`, `.claude/kb/seguranca-local/` |
| Rule de domínio | `.claude/rules/financeiro.md` |
| Rubrica do revisor externo | `docs/revisao/rubrica-adversarial.md` |
| Contratos de teste | `tests/contracts/invariantes.yaml`, `tests/contracts/criterios.yaml`, `fixtures/numericos.yaml` |

## A fazer pelo usuário

- **Persistir deny/ask/hooks** em `.claude/settings.json` conforme o ADR 019 (blocos A e B). O agente não faz isso por ele.
- **Buscar skills** nos catálogos públicos (skills.sh, skillsmp), revisando cada uma antes de instalar:

| Assunto | O que a skill precisa cobrir | Termos de busca |
|---|---|---|
| Frontend React + TypeScript | Estrutura de app, formulários dinâmicos com validação, tipagem estrita | react typescript, react hook form zod |
| PWA | Manifest, service worker, instalação no Chrome Android, limites offline | pwa, service worker, web app manifest |
| Cliente tipado a partir do contrato | Gerar cliente TypeScript do OpenAPI do FastAPI | openapi typescript client, fastapi openapi |
| Segurança de aplicação web | Checklist OWASP, validação de entrada, API local (CORS, token) | owasp, web app security review, fastapi security |
| Segredos e scanner | `.env`, gitleaks, higiene de commit | secrets management, gitleaks |
| Backup e restauração de Postgres | `pg_dump`, restauração testada, criptografia com age | postgres backup restore, pg_dump |
| Migrações de banco | Versionar esquema, reverter | database migrations, alembic |
| Dinheiro e ledger | Dupla entrada, precisão decimal, arredondamento | double entry ledger, money decimal precision |
| Postgres de produção | `NUMERIC`, constraints, índices, boas práticas | postgresql best practices |

## Agentes e KBs genéricos reaproveitados

`sql-architect`, `schema-designer`, `sql-optimizer`, `revisor-codigo`, KBs `sql-patterns`, `fastapi`, `testing`, `data-modeling`. O restante da frota (Spark, Databricks, streaming, Airflow etc.), `data-engineering.yaml` e o gate de data-check ficam **em standby**: não são usados e não atrapalham, e mantê-los evita divergência com o harness canônico.

## Pendente

- Definir o comando `check` e o script de rastreabilidade (SPEC-001).
- Fixar versões das dependências (SPEC-001).
