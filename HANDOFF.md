# Handoff — sisfin

> Gerado pelo install-harness em 2026-10-16. Atualize a cada handoff de sessão.

## Estado atual

- Brainstorm e decisões concluídos: ADRs 006–023 aceitas (`docs/adr/`), invariantes INV-01..26 e fixtures em `tests/contracts/` e `fixtures/`, rubrica do revisor em `docs/revisao/`, PRD rascunhado em `.claude/projetos/sisfin/`.
- Harness instalado; contexto (`CLAUDE.md`, `AGENTS.md`, `CONTEXT.md`, `README.md`) preenchido a partir das decisões. Nenhum código ainda.
- Repositório GitHub: `sisfin` (será público; `main` protegida, alterações via PR). Trabalho de contexto na branch `chore/contexto-sisfin`.

## Próximos passos

1. Terminar o `/grill-me` (lacunas listadas em `.claude/projetos/sisfin/01-grill.md`).
2. Escrever SPEC-001 (esquema base, papéis, banco tst, fixtures) com critérios em `tests/contracts/criterios.yaml`.
3. Implementar na ordem das SPECs do `02-prd.md`.
