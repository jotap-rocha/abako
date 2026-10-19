# abako — Harness

> Decisões de harness do projeto (ADR 016, 019, 024). Estado (revisão de 2026-10-19, `harness-design`): artefatos criados e conferidos contra o disco; reflete SPECs 001..014 e ADRs 026–032. Sem scaffold novo: só ajustes pontuais (ver "Deriva corrigida"). Adversarial-judge via OpenRouter não usado por decisão do usuário (revisão adversarial feita manualmente).

## Deriva corrigida (2026-10-19)

| Onde | Deriva | Correção |
|---|---|---|
| `kb/seguranca-local/backup-restore.md` | restaurava em `tst` (contradiz ADR 032: banco descartável dedicado, alvo `prd` recusado) | texto alinhado ao ADR 032 |
| `kb/postgres-financeiro/ledger-dinheiro.md` | sem D1/D4 (visão corrigida, versão vigente única, controle otimista, idempotência) | seção "Tempo, concorrência e idempotência" |
| `rules/pipeline.md` | sem trava de execução única | `pg_advisory_lock` (ADR 029) |
| `kb/react-pwa/pwa.md` | sem limpeza de cache no logout nem escopo online/PC (ADR 031) | duas linhas |
| `02-prd.md` | faltava seção SI Considerations; banco de restauração não citado | adicionados |
| `.cursor/` espelhos | rules/KBs editados acima e `projetos/abako/*` defasados | sincronizados |

## Lacunas conhecidas, deliberadamente não preenchidas

- Sem agente/skill novos: nenhuma lacuna real. Backup/restauração e migrações ficam nas KBs e nas skills já travadas; a SPEC-001 detalha.
- `scripts/check`, rastreabilidade, `db/`, `backend/`, `frontend/`, `pipeline/`, `tests/` (além de `contracts/`) não existem ainda: nascem nas SPECs (001 em diante).
- `criterios.yaml` vazio por desenho; fixtures novas nas SPEC-003 e 005.
- Papel/permissão para o script de restauração criar e remover o banco descartável: o `settings.json` nega `dropdb`; definir na SPEC-001 como o script faz isso (ver dúvidas no relatório).

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
- Backup criptografado (age) com teste de restauração num banco descartável dedicado do mesmo contêiner, recusando o alvo `prd` (D7, ADR 032); definir na SPEC-001 retenção, local da chave e se roda no `check` ou na rotina de deploy local.
- SPECs renumeradas 001..014 (2026-10-18, revisão adversarial): login na 002, gasto real na 008, vale e R5 na 013, pipeline na 014. Ver `02-prd.md`.
- Fixar versões das dependências (SPEC-001). Porta do Postgres do projeto: **5433**.
- gitleaks 8.30.1 instalado e ligado ao pre-commit (`.githooks/pre-commit`, `.gitleaks.toml`). Também roda no CI.
- Conferir versões/flags das ferramentas citadas nas KBs via context7 ao implementar.
