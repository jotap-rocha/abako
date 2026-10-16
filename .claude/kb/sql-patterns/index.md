---
domain: sql-patterns
description: SQL cross-dialect (Postgres/Snowflake/BigQuery/DuckDB) — leitura de query plan, otimização e análise de queries existentes
mcp_validated: null
confidence: null
---

# KB: SQL Patterns

Base de conhecimento de **otimização e análise** de queries SQL já escritas — não é sobre
desenhar uma query nova (isso é `sql-architect`, ver `.claude/agents/architect/sql-architect.md`).
Cobre leitura de plano de execução, custo de join, window functions, CTEs e diagnóstico
de query lenta em Postgres, Snowflake, BigQuery e DuckDB.

## Conformidade DE (ponte)

Fonte: `data-engineering.yaml` — este KB **não** duplica severidade nem texto normativo.

| Âncora | Relação |
|---|---|
| `DE-A*` | Universal |
| pacote **D** | se a tree for cloud |

## Fronteira com outros domínios

- **Query nova / design de SELECT / RLS / N+1 / paginação básica** → `sql-architect` (agente) —
  não duplicado aqui.
- **Dado exato vs busca semântica, padrão LEDGER** → `.claude/kb/rag/patterns/ledger-lookup.md`.
- **Este domínio** → você já tem uma query (sua ou de terceiro) rodando devagar ou precisa
  entender/portar entre engines — o foco é diagnóstico e otimização.

## Conceitos

| Arquivo | Tópico |
|---|---|
| [query-plan-reading.md](concepts/query-plan-reading.md) | Ler `EXPLAIN ANALYZE` — seq scan, nested loop, custo, linhas estimadas vs reais |
| [window-functions.md](concepts/window-functions.md) | `OVER()`, partição, frame, ranking — quando substituem self-join/subquery |
| [cte-recursive-vs-materialized.md](concepts/cte-recursive-vs-materialized.md) | CTE recursiva (hierarquias) vs `MATERIALIZED`/`NOT MATERIALIZED` — custo por engine |
| [join-types-costs.md](concepts/join-types-costs.md) | Nested loop, hash join, merge join — quando o planner escolhe cada um e por quê |

## Padrões

| Arquivo | Tópico |
|---|---|
| [slow-query-diagnosis.md](patterns/slow-query-diagnosis.md) | Checklist diagnóstico passo a passo — do sintoma à causa raiz |
| [dialect-translation.md](patterns/dialect-translation.md) | Tradução de funções de data/string/window entre Postgres, Snowflake, BigQuery, DuckDB |
| [efficient-pagination.md](patterns/efficient-pagination.md) | Cursor/keyset vs offset a fundo — quando cada um degrada e por quê |
| [composite-indexing.md](patterns/composite-indexing.md) | Ordem de colunas, index-only scan, índice parcial e covering index |

## Quick Reference

Ver [quick-reference.md](quick-reference.md) — cheatsheet de leitura de `EXPLAIN`, tabela de
custo por tipo de join/scan, decision tree "por onde começar o diagnóstico". Ler só se a tarefa
exigir esse nível de detalhe operacional.

## Nota de validação

Este domínio foi criado sem acesso à Context-7 MCP nesta sessão (`mcp_validated`/`confidence`
ficam `null` — não inventados). Rode uma auditoria (Modo 2 do `kb-architect`) assim que o MCP
estiver disponível para validar contra a documentação oficial de cada engine.
