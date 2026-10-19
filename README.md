> **Este repositório é o projeto `abako`, não o Agent Harness Canônico.**
> Não copie o guia do repositório canônico do harness. Refine com `/grill-me`, `/grill-with-docs` ou `harness-architect`.

# abako

Sistema financeiro pessoal, local-first. Responde: quanto tenho em cada conta, quanto estou gastando de verdade e se o orçamento do mês está apertado ou folgado.

> Projeto em fase de especificação.

## Visão geral

- **Ledger** de transações com histórico de versões e conferência por snapshot de saldo.
- **Cartões e faturas** com parcelas, linha de crédito compartilhada, estorno e despesas de terceiros (com "a receber").
- **Reserva** com meta em meses de gasto essencial e níveis (crítica / atenção / saudável).
- **Compromissos vs. disponível** no horizonte do R2 (parâmetro, inicial 10 dias), com alerta de sobra negativa.
- **Conta de benefício** (vale) separada do gasto real, com bolsos e sobra.

## Arquitetura

React + TypeScript (PWA) → FastAPI → PostgreSQL (`prd`/`tst`) → pipeline Python → DuckDB analítico (só agregados). Tudo em `localhost`.

## Documentação

- `docs/adr/` — decisões (ADRs 006–032)
- `tests/contracts/` e `fixtures/` — invariantes, critérios e fixtures numéricas
- `CONTEXT.md` — glossário do domínio e da web
- `docs/revisao/rubrica-adversarial.md` — rubrica da revisão adversarial
- `.claude/projetos/abako/` — ideia, grill, PRD e plano do harness
