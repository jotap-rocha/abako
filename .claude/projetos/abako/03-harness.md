# abako — Harness

> Decisões de harness do projeto (ADR 016, 019, 024). Estado: artefatos do projeto criados; o `harness-architect` ainda não rodou.

## Já criado

| Artefato | Caminho |
|---|---|
| Agentes | `.claude/agents/fin/`: `abako-especialista` (contexto de negócio), `fin-frontend`, `fin-backend`, `fin-db`, `fin-pipeline`, `fin-seguranca` |
| KBs | `.claude/kb/`: `react-pwa`, `postgres-financeiro`, `seguranca-local`, `duckdb-analitico` (cada uma com tópicos detalhados) |
| Skills (skills.sh) | `.claude/skills/`, travadas em `skills-lock.json` — ver tabela abaixo |
| Rules | `.claude/rules/`: `financeiro`, `backend`, `frontend`, `testes`, `pipeline` |
| Guardrails | `agent-policies.yaml` (família `abako`) + `.claude/settings.json` (deny, ask, hooks Bash e PowerShell) — ADR 024 |
| Rubrica do revisor externo | `docs/revisao/rubrica-adversarial.md` |
| Contratos de teste | `tests/contracts/`, `fixtures/numericos.yaml` |

Tudo espelhado em `.cursor/`.

## Skills instaladas do skills.sh

Instaladas com `npx skills add <repo> -s <skill>` (cópia, não symlink) e auditadas por busca de padrões perigosos: só Markdown, sem scripts. Revisão de conteúdo recomendada.

| Assunto | Skill | Repositório |
|---|---|---|
| Postgres (esquema, SQL, migrações) | `supabase-postgres-best-practices` | supabase/agent-skills |
| Postgres (tabelas, tipos, constraints) | `postgresql-table-design` | wshobson/agents |
| Migrações (genérica) | `database-migration` | wshobson/agents |
| FastAPI | `fastapi-templates` | wshobson/agents |
| Cliente TS do OpenAPI | `openapi-ts-client` | bm629/agent-skills |
| PWA | `pwa-development` | alinaqi/claude-bootstrap |
| TypeScript / React / Python | `typescript-best-practices`, `react-best-practices`, `python-best-practices` | 0xbigboss/claude-code |
| Segredos | `secrets-scan` | jwynia/agent-skills |
| gitleaks | `implementing-secret-scanning-with-gitleaks` | mukul975/Anthropic-Cybersecurity-Skills |
| Backup | `database-backups` | bagelhole/devops-security-agent-skills |
| Integridade/restauração de backup | `validating-backup-integrity-for-recovery` | mukul975/Anthropic-Cybersecurity-Skills |

Sem skill pronta no skills.sh para: ledger/dinheiro com precisão decimal, migrações Alembic em SQL puro (a skill `alembic` do bm629 pressupõe ORM e autogenerate, contrário ao ADR 025), segurança de sessão FastAPI e DuckDB. Esses conteúdos ficam nas KBs (`ledger-dinheiro`, `migracoes`, `api-seguranca`, `pipeline`).

## Agentes e KBs genéricos reaproveitados

`sql-architect`, `schema-designer`, `sql-optimizer`, `revisor-codigo`, KBs `sql-patterns`, `fastapi`, `testing`, `data-modeling`. O restante da frota (Spark, Databricks, streaming, Airflow etc.), `data-engineering.yaml` e o gate de data-check ficam **em standby**.

## CI mínimo (ADR 022)

`.github/workflows/ci.yml`: `gitleaks` (histórico + árvore, binário com checksum fixo), `workflows` (actionlint + zizmor) e `contratos` (`scripts/validar_contratos.py` + `agent_policies check`). Ações fixadas por SHA, permissões mínimas, sem segredos; Dependabot semanal para ações. O `check` completo (ruff, mypy, pytest, Vitest, Playwright, Postgres efêmero) entra com a SPEC-001. Branch protection exige os 3 checks depois do primeiro run.

## Pendente

- Definir o comando `check` e o script de rastreabilidade (SPEC-001).
- Fixar versões das dependências (SPEC-001). Porta do Postgres do projeto: **5433**.
- gitleaks 8.30.1 instalado e ligado ao pre-commit (`.githooks/pre-commit`, `.gitleaks.toml`). Também roda no CI.
- Conferir versões/flags das ferramentas citadas nas KBs via context7 ao implementar.
