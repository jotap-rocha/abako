> **Este repositório é o projeto `abako`, não o Agent Harness Canônico.**
> Não copie o guia do repositório canônico do harness. Refine com `/grill-me`, `/grill-with-docs` ou `harness-architect`.

# abako — espelho portátil (Cursor/Windsurf/Codex)

Sistema financeiro pessoal local-first (saldos, gasto real, orçamento, reserva, cartões). Sem referências a `.claude/`.

## Stack

React + TypeScript (PWA, cliente gerado do OpenAPI) · FastAPI · PostgreSQL local (`prd`/`tst`) com regras financeiras em views/funções SQL · analítico em DuckDB, arquivo separado (só agregados) · pipeline Python · pytest, Hypothesis, Vitest + RTL, Playwright.

## Comandos

- `check` — validação única (lint + tipos + testes + rastreabilidade). A definir na SPEC-001.

## Invariantes

Fonte: `tests/contracts/invariantes.yaml` (INV-01..26) + `fixtures/numericos.yaml`. Essenciais:

- Dinheiro nunca é float (NUMERIC/Decimal; JSON como texto).
- Ledger com versões (SCD2), exclusão lógica; saldo derivado = último snapshot + transações válidas posteriores; divergência só sinalizada.
- Transferência = 2 pernas, soma zero. Gasto real exclui transferência, investimento, repasse, rendimento, pagamento de fatura, terceiros e conta de benefício.
- Parcelas somam o total (última absorve centavos); limite consome o valor total da compra.
- Toda tabela tem `user_id`; toda consulta filtra pelo `user_id` da sessão.
- Analítico unidirecional (transacional → analítico, só agregados).
- Datas civis em `America/Sao_Paulo`. Nenhuma regra financeira no front.

## SI

Dados financeiros pessoais reais. `prd` somente leitura para agentes; escrita só em `tst`. Nunca ler/escrever `.env`, dados ou backups. Sem credencial bancária. Serviços só em `127.0.0.1`. Sem commit/push sem acordo explícito.
