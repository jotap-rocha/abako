---
topic: slow-query-diagnosis
confidence: null
mcp_validated: null
---

# Diagnóstico de Query Lenta — Passo a Passo

Checklist ordenado. Pare no primeiro passo que revelar a causa — nem toda query lenta precisa
percorrer todos os passos.

## Passo 1 — Meça e leia o plano real

```sql
EXPLAIN (ANALYZE, BUFFERS) <query>;   -- Postgres/DuckDB
-- Snowflake: rode a query, abra Query Profile na UI
-- BigQuery: rode a query, abra "Execution details"
```

Sem isso, qualquer mudança é aposta. Ver `../concepts/query-plan-reading.md` para interpretar
a saída. **Nunca pule este passo.**

## Passo 2 — Compare linhas estimadas vs reais

Gap grande (ordem de magnitude) = estatísticas desatualizadas ou predicado não sargeável.

```sql
-- Postgres: força atualização de estatísticas
ANALYZE produtos;

-- Predicado NÃO sargeável (impede uso de índice) — comum:
WHERE EXTRACT(YEAR FROM created_at) = 2026        -- função na coluna
WHERE UPPER(nome) = 'PRODUTO X'                    -- função na coluna
WHERE preco + 10 > 100                             -- expressão na coluna

-- Sargeável (permite índice):
WHERE created_at >= '2026-01-01' AND created_at < '2027-01-01'
WHERE nome = 'PRODUTO X'   -- + índice em LOWER(nome) se busca case-insensitive
WHERE preco > 90
```

## Passo 3 — Identifique o nó mais caro no plano

Procure o nó com maior `actual time` (não `cost`) — geralmente o filho mais profundo com
`loops` alto ou `Rows Removed by Filter` alto.

| Nó problemático | Causa provável | Ação |
|---|---|---|
| `Seq Scan` com filtro seletivo | Falta índice | `../patterns/composite-indexing.md` |
| `Nested Loop` com `loops` alto | Lado interno sem índice | Índice na coluna de join |
| `Sort` caro (`external merge`) | `work_mem`/memória insuficiente para o volume | Aumentar memória de sort, ou índice que já entrega ordenado |
| `Hash` com `Batches > 1` | Hash table maior que a memória disponível | Filtrar antes, aumentar `work_mem`, ou reduzir colunas selecionadas |
| `WindowAgg` + `Sort` repetido | Múltiplas window functions com partições diferentes | Unificar em `WINDOW` nomeada — ver `../concepts/window-functions.md` |

## Passo 4 — Verifique se o índice existe e é usado

```sql
-- Postgres: índices existentes na tabela
SELECT indexname, indexdef FROM pg_indexes WHERE tablename = 'produtos';

-- Índice existe mas planner não usa? Possíveis causas:
-- (a) seletividade baixa — planner prefere Seq Scan (correto para tabela pequena)
-- (b) estatísticas desatualizadas fazem parecer não seletivo
-- (c) tipo de dado incompatível (cast implícito)
-- (d) função aplicada à coluna sem índice de expressão correspondente
```

Ver `../patterns/composite-indexing.md` para desenhar o índice certo.

## Passo 5 — Verifique se é a query ou é volume/infraestrutura

```sql
-- Quantas linhas a tabela realmente tem?
SELECT reltuples::bigint FROM pg_class WHERE relname = 'produtos';  -- Postgres, estimativa rápida

-- Snowflake/BigQuery: verificar se o warehouse/slot é o gargalo, não a query
-- Snowflake: checar "Queued" time no histórico — fila de warehouse, não a query em si
-- BigQuery: checar "Slot time consumed" — mais slots ≠ sempre mais rápido se query é I/O-bound
```

Se a query já está com plano ótimo (índices certos, join eficiente) e ainda é lenta por
volume genuíno de dados, o problema não é a query — é arquitetura (particionamento,
pré-agregação, cache, ou revisar se a consulta precisa mesmo processar esse volume).

## Passo 6 — Aplique UMA mudança por vez e remeça

```
1. Aplicar mudança (índice, reescrita, hint)
2. Rodar EXPLAIN ANALYZE de novo
3. Comparar actual time antes/depois
4. Se não melhorou (ou piorou): reverter, tentar próxima hipótese
```

Nunca aplique múltiplas mudanças simultâneas — impossível saber qual causou o efeito
(positivo ou negativo).

## Anti-padrões comuns de "otimização" que não otimizam

```sql
-- ERRADO: adicionar índice sem checar se já existe um similar
-- (índices redundantes custam escrita e espaço sem ganho de leitura)

-- ERRADO: SELECT * quando só 3 colunas são usadas
-- (impede Index Only Scan; aumenta I/O e rede)
SELECT * FROM produtos WHERE categoria_id = 5;
-- CERTO:
SELECT id, nome, preco FROM produtos WHERE categoria_id = 5;

-- ERRADO: LIMIT sem ORDER BY determinístico (resultado pode mudar entre execuções,
-- e não necessariamente é mais rápido se o plano ainda escaneia tudo antes de cortar)
SELECT * FROM pedidos LIMIT 10;  -- sem WHERE nem ORDER BY = sem garantia nenhuma
```

## Referências
- `../concepts/query-plan-reading.md` — passo 1 em detalhe
- `../concepts/join-types-costs.md` — passo 3, nós de join
- `../patterns/composite-indexing.md` — passo 4, desenho de índice
- `../patterns/efficient-pagination.md` — se o sintoma é "página alta fica lenta"
