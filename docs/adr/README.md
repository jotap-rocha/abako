# Architecture Decision Records

Registro de decisões arquiteturais significativas deste projeto.

Criadas via `/new-adr` (skill `.claude/skills/new-adr/`). ADRs são **imutáveis**: uma decisão
revista não é editada — ganha uma ADR nova que a substitui.

## Decisões

| # | Título | Status | Data |
|---|---|---|---|
| [001](001-sincronia-de-contexto-no-fechamento.md) | Sincronia de contexto no fechamento do fluxo | Aceita | 2026-08-05 |
| [002](002-pacote-e-keyvault-cloud-dual-install.md) | Pacote E keyvault-cloud + skill dual + install vault | Aceita | 2026-08-12 |
| [003](003-kernel-agent-policies-dual-runtime.md) | Kernel agent-policies dual-runtime (deny/ask + foundation) | Aceita | 2026-08-13 |
| [004](004-kernel-evidence-gate.md) | Kernel evidence-gate (collect/check + foundation) | Aceita | 2026-08-13 |
| [005](005-kernel-fluxo-events.md) | Kernel fluxo-events (telemetria live SDD) | Aceita | 2026-08-13 |
| [006](006-ledger-historico-snapshot.md) | Ledger de transações, histórico e snapshot de saldo | Aceita | 2026-10-16 |
| [007](007-reserva-financeira.md) | Reserva financeira como conta dedicada com meta em meses | Aceita | 2026-10-16 |
| [008](008-camada-analitica-separada.md) | Camada analítica fisicamente separada | Aceita | 2026-10-16 |
| [009](009-terceiros-e-repasse.md) | Uso por terceiros e repasse | Aceita | 2026-10-16 |
| [010](010-entrada-de-dados-manual.md) | Entrada de dados manual na v1 | Aceita | 2026-10-16 |
| [011](011-tipos-de-transacao-parcelas-e-limite.md) | Tipos de transação, parcelas e limite | Aceita | 2026-10-16 |
| [012](012-modelo-de-dados-e-views-analiticas.md) | Modelo de dados e views analíticas | Aceita | 2026-10-16 |
| [013](013-estorno-e-competencia-da-fatura.md) | Estorno e competência da fatura | Aceita | 2026-10-16 |
| [014](014-plataforma-local-first.md) | Plataforma local-first, bancos prd e tst | Aceita | 2026-10-16 |
| [015](015-stack.md) | Stack: React + TypeScript, FastAPI, pipeline Python | Aceita | 2026-10-16 |
| [016](016-frota-de-agentes-skills-e-kbs.md) | Frota de agentes, skills e KBs do projeto | Aceita | 2026-10-16 |
| [017](017-revisor-adversarial.md) | Revisor adversarial externo | Aceita | 2026-10-16 |
| [018](018-gestao-de-segredos.md) | Gestão de segredos com `.env` e gitleaks | Aceita | 2026-10-16 |
| [019](019-guardrails-dos-agentes.md) | Guardrails dos agentes | Aceita | 2026-10-16 |
| [020](020-autenticacao.md) | Autenticação | Aceita | 2026-10-16 |
| [021](021-estrutura-do-repositorio-e-testes.md) | Estrutura do repositório e estratégia de testes | Aceita | 2026-10-16 |
| [022](022-repositorio-publico-ci-cd.md) | Repositório público, CI/CD e escopo da documentação | Aceita | 2026-10-16 |
| [023](023-reserva-r2-recorrentes-e-vale.md) | Reserva, compromissos vs. disponível, recorrentes e vale | Aceita | 2026-10-16 |
| [024](024-guardrails-implementacao.md) | Implementação dos guardrails dos agentes | Aceita | 2026-10-17 |
| [025](025-migracoes-alembic-sql.md) | Migrações do Postgres com Alembic em SQL puro | Aceita | 2026-10-17 |
| [026](026-semantica-temporal-edicao-retroativa.md) | Semântica temporal da edição retroativa e snapshots | Aceita | 2026-10-19 |
| [027](027-fechamento-em-dia-inexistente.md) | Fechamento do cartão em dia inexistente e compra no dia do fechamento | Aceita | 2026-10-19 |
| [028](028-ordem-das-specs-001-014.md) | Ordem e renumeração das SPECs (001..014) | Aceita | 2026-10-19 |
| [029](029-concorrencia-e-idempotencia.md) | Concorrência e idempotência como garantias de esquema | Aceita | 2026-10-19 |
| [030](030-compra-100-por-cento-e-repasse-excedente.md) | Compra 100% própria ou 100% de terceiro e repasse excedente | Aceita | 2026-10-19 |
| [031](031-seguranca-local-e-pwa-online.md) | Segurança local da API e PWA online | Aceita | 2026-10-19 |
| [032](032-backup-com-restauracao-testada.md) | Backup com restauração testada na v1 | Aceita | 2026-10-19 |
| [033](033-frontend-fino-antecipado.md) | Frontend fino antecipado (SPEC-012 em incrementos) | Aceita | 2026-10-19 |
| [034](034-reserva-bruto-liquido.md) | Reserva em bruto e líquido, com imposto retido | Aceita | 2026-10-19 |
| [035](035-endereco-abako-localhost.md) | Endereço local `abako.localhost` | Aceita | 2026-10-19 |
