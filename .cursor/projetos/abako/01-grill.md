# abako — Grill

> Consolidado a partir do brainstorm do usuário. As decisões vivem nos ADRs 006–023 (`docs/adr/`); aqui ficam o checklist de completude, as decisões em uma linha e as lacunas.

## Checklist de completude

- [x] **Problema real:** o saldo é conferido manualmente em planilha; falta visão de gasto real e de folga do orçamento (ADR 006).
- [x] **Usuário:** uma pessoa (o próprio dono). `user_id` preparado para multiusuário futuro, não funcional (ADR 006, 012).
- [x] **Critérios de sucesso mensuráveis:** invariantes INV-01..26 e fixtures numéricas (`tests/contracts/`, `fixtures/`).
- [x] **Out of scope declarado:** ver `02-prd.md`.
- [x] **Restrições técnicas:** local-first, Windows 11, Docker, Android antigo só como futuro (ADR 014).
- [x] **SLA / performance:** sem SLA formal; volume pequeno (ADR 008). Se surgir necessidade, entra como evolução contínua.

## Decisões (uma linha cada)

| ADR | Decisão |
|---|---|
| 006 | Ledger com versões (SCD2), snapshot de saldo, `user_id`, cartão ≠ linha de crédito |
| 007 | Reserva = conta dedicada + meta em meses |
| 008 | Analítico em DuckDB (arquivo separado), só agregados, fluxo unidirecional |
| 009 | Terceiros: `pessoa` na transação; repasse abate o "a receber" |
| 010 | Entrada manual na v1; sem credencial bancária |
| 011 | 7 tipos de transação; parcelas por linha; limite pelo total |
| 012 | Modelo de dados; `NUMERIC`; data civil `America/Sao_Paulo` |
| 013 | Estorno integral vs. com parcelas pagas; fechamento com vigência |
| 014 | Local-first; bancos `prd`/`tst`; risco de dado real assumido |
| 015 | React+TS PWA, FastAPI, Postgres + DuckDB, pipeline Python, regra em SQL; SQLite rejeitado |
| 016 | Frota enxuta: `fin-frontend` + 3 KBs |
| 017 | Revisor adversarial externo, 1 passada + 1 reteste |
| 018 | `.env` + gitleaks; backup com age |
| 019 | Guardrails: deny / ask / papéis no banco |
| 020 | Argon2id, sessão no servidor, CSRF, CORS, rate limit |
| 021 | Testes: pytest, Hypothesis, Vitest+RTL, Playwright; comando `check` |
| 022 | Repositório público, CI sem segredos, deploy local manual |
| 023 | Reserva (níveis), R2, recorrentes e vale |

## Lacunas abertas (para o /grill-me)

1. ~~R5~~ — resolvido: alerta do vale quando o `resta` de um bolso fica negativo (ADR 023).
2. ~~Horizonte do R2~~ — resolvido: parâmetro com vigência, inicial 10 dias (ADR 023).
3. **Pendências externas** (não bloqueiam as SPECs iniciais): formatos de exportação dos bancos; bruto vs. líquido da reserva; datas de fechamento e semântica de limite dos cartões; disponibilidade do modelo revisor.
4. ~~SLA / performance~~ — resolvido: sem SLA formal; tratar como evolução contínua se surgir.
5. ~~Estrutura de pastas e Docker~~ — resolvido: estrutura em `CLAUDE.md`; Docker Desktop; contêiner Postgres dedicado ao projeto (ADR 014).
6. **Comando `check`** e script de rastreabilidade: definir na SPEC-001.
7. ~~Rules genéricas~~ — resolvido: `backend`, `frontend`, `testes` e `pipeline` adaptadas ao abako.
