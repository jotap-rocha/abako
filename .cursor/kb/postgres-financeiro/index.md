---
domain: postgres-financeiro
description: Postgres para domínio financeiro — NUMERIC, constraints de ledger, SCD2 por vigência, views de saldo/fatura/limite, papéis e datas civis
mcp_validated: null
confidence: null
---

# KB: Postgres financeiro

Complementa `.claude/kb/sql-patterns/` (genérico) com o que é específico do abako. Decisões nos ADRs 006, 008, 011, 012, 013 e 019.

## Tópicos cobertos

- **`NUMERIC`** com escala definida na SPEC-001; nunca float.
- **Constraints** para as invariantes do ledger.
- **SCD2 por vigência** (válido de/até) e exclusão lógica.
- **Transferência em duas pontas** com soma zero.
- **Views SQL** para saldo derivado, fatura e limite.
- **Datas:** `timestamptz` para instantes e **data civil em `America/Sao_Paulo`** para datas de negócio.
- **Papéis:** a aplicação sem `UPDATE/DELETE` nas tabelas de versão; o pipeline lê o transacional por papel somente leitura. O analítico é DuckDB (ADR 008), fora deste KB.
- **Snapshot** de saldo e conferência; testes com pgTAP/pytest.

## Fronteiras

- Diagnóstico de query lenta → `.claude/kb/sql-patterns/`.
- Design de SELECT/RLS/N+1 → agente `sql-architect`.
- Modelagem de histórico (SCD) → agente `schema-designer`.

## Tópicos detalhados

| Arquivo | Tópico |
|---|---|
| [ledger-dinheiro.md](ledger-dinheiro.md) | Ledger e dinheiro: parcelas, saldo derivado, versões, estorno |
| [migracoes.md](migracoes.md) | Migrações Alembic em SQL puro (ADR 025) |

## Quick Reference

Ver [quick-reference.md](quick-reference.md).

## Nota de validação

Criado sem acesso à Context-7 MCP (`mcp_validated`/`confidence` ficam `null`). Escalas, nomes de constraint e DDL serão definidos na SPEC-001.
