---
domain: sql-patterns
topic: quick-reference
---

# SQL Patterns — Quick Reference

### Decision tree: por onde começar o diagnóstico de query lenta

```
Query lenta — por onde começar?
├── Nunca rodou EXPLAIN ANALYZE?
│   └── Rode primeiro → concepts/query-plan-reading.md
├── Linhas estimadas ≠ linhas reais (grande gap)?
│   └── Estatísticas desatualizadas → ANALYZE table / atualizar stats do engine
├── Seq Scan / Full Table Scan em tabela grande com filtro seletivo?
│   └── Falta índice → patterns/composite-indexing.md
├── Nested Loop com muitas iterações no lado externo?
│   └── Join mal ordenado ou falta índice no lado interno → concepts/join-types-costs.md
├── OFFSET alto (paginação por página numérica)?
│   └── patterns/efficient-pagination.md
└── Combinação dos acima ou causa não óbvia?
    └── Checklist completo → patterns/slow-query-diagnosis.md
```

### Cheatsheet: nós de EXPLAIN e o que significam

| Nó | Significa | Bandeira vermelha |
|---|---|---|
| `Seq Scan` | Leu a tabela inteira | Filtro seletivo sem índice correspondente |
| `Index Scan` | Usou índice, foi buscar linha na tabela | OK, mas `Index Only Scan` é melhor se possível |
| `Index Only Scan` | Índice cobre todas as colunas pedidas | Ideal — sem heap fetch |
| `Nested Loop` | Para cada linha externa, busca na interna | OK se lado externo é pequeno; ruim se grande |
| `Hash Join` | Constrói hash table de um lado, sonda do outro | Bom para joins grandes sem ordem |
| `Merge Join` | Ambos os lados ordenados, mescla | Bom quando já há índice/ordem nas duas pontas |
| `Sort` | Ordenação explícita, custa memória/disco | Verificar `work_mem` se `external merge` aparecer |
| `Bitmap Heap Scan` | Combina múltiplos índices via bitmap | Normal para filtros compostos com OR |

### Custo relativo por tipo de join (ordem de grandeza)

| Join | Melhor quando | Custo |
|---|---|---|
| Nested Loop | Lado externo pequeno (< ~100 linhas) | O(N × M) sem índice; O(N × log M) com índice |
| Hash Join | Sem ordem prévia, tabelas médias/grandes | O(N + M), mas custa memória |
| Merge Join | Ambos lados já ordenados (ou índice cobre) | O(N + M), quase sem memória extra |

### Sintomas → engine-specific quick fix

| Sintoma | Postgres | Snowflake | BigQuery | DuckDB |
|---|---|---|---|---|
| Stats desatualizadas | `ANALYZE tabela` | auto (mas força com `ALTER TABLE ... REFRESH`) | auto | `ANALYZE` |
| Plano | `EXPLAIN (ANALYZE, BUFFERS)` | `EXPLAIN` + Query Profile na UI | `EXPLAIN` / execution details na UI | `EXPLAIN ANALYZE` |
| Índice faltando | `CREATE INDEX CONCURRENTLY` | clustering key (não é índice tradicional) | particionamento/clustering de tabela | `CREATE INDEX` |
| Scan explode custo | checar `work_mem`, `random_page_cost` | checar warehouse size (compute) | checar bytes scanned (custo $) | checar `memory_limit` |

### Regra de ouro

Nunca otimize sem medir antes/depois. Rode `EXPLAIN ANALYZE` (ou equivalente) antes da mudança,
aplique uma mudança por vez, meça de novo. Ver `patterns/slow-query-diagnosis.md`.
