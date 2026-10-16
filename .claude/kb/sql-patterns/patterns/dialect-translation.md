---
topic: dialect-translation
confidence: null
mcp_validated: null
---

# Tradução de Dialeto SQL (Postgres / Snowflake / BigQuery / DuckDB)

Referência rápida para portar query entre engines sem reescrever a lógica do zero.

## Data/hora — "hoje" e diferença de dias

| Operação | Postgres | Snowflake | BigQuery | DuckDB |
|---|---|---|---|---|
| Data atual | `CURRENT_DATE` | `CURRENT_DATE()` | `CURRENT_DATE()` | `CURRENT_DATE` |
| Timestamp atual | `now()` | `CURRENT_TIMESTAMP()` | `CURRENT_TIMESTAMP()` | `now()` |
| Soma de intervalo | `data + interval '7 days'` | `DATEADD(day, 7, data)` | `DATE_ADD(data, INTERVAL 7 DAY)` | `data + interval '7 days'` |
| Diferença em dias | `data2 - data1` | `DATEDIFF(day, data1, data2)` | `DATE_DIFF(data2, data1, DAY)` | `data2 - data1` |
| Extrair parte | `EXTRACT(month FROM data)` | `DATE_PART(month, data)` | `EXTRACT(MONTH FROM data)` | `EXTRACT(month FROM data)` |
| Truncar para mês | `date_trunc('month', data)` | `DATE_TRUNC('month', data)` | `DATE_TRUNC(data, MONTH)` | `date_trunc('month', data)` |
| Formatar string | `to_char(data, 'YYYY-MM-DD')` | `TO_VARCHAR(data, 'YYYY-MM-DD')` | `FORMAT_DATE('%Y-%m-%d', data)` | `strftime(data, '%Y-%m-%d')` |

```sql
-- Exemplo: "pedidos dos últimos 30 dias" nos 4 engines
-- Postgres/DuckDB
WHERE created_at >= CURRENT_DATE - interval '30 days'
-- Snowflake
WHERE created_at >= DATEADD(day, -30, CURRENT_DATE())
-- BigQuery
WHERE created_at >= DATE_SUB(CURRENT_DATE(), INTERVAL 30 DAY)
```

## String — concatenação e case

| Operação | Postgres | Snowflake | BigQuery | DuckDB |
|---|---|---|---|---|
| Concatenar | `a \|\| b` | `a \|\| b` ou `CONCAT(a,b)` | `CONCAT(a,b)` (`\|\|` também funciona) | `a \|\| b` |
| Case-insensitive | `ILIKE` | `ILIKE` | não existe `ILIKE` — usar `LOWER(a) LIKE LOWER(b)` | `ILIKE` |
| Substring | `substring(s from 1 for 3)` | `SUBSTR(s, 1, 3)` | `SUBSTR(s, 1, 3)` | `substring(s, 1, 3)` |
| Split em array | `string_to_array(s, ',')` | `SPLIT(s, ',')` | `SPLIT(s, ',')` | `string_split(s, ',')` |

## Window functions com filtro pós-agregação (`QUALIFY`)

```sql
-- Snowflake / BigQuery / DuckDB: QUALIFY filtra direto o resultado de window function
SELECT *, ROW_NUMBER() OVER (PARTITION BY cliente_id ORDER BY data DESC) AS rn
FROM pedidos
QUALIFY rn = 1;

-- Postgres: não existe QUALIFY — precisa de CTE/subquery
WITH ranked AS (
  SELECT *, ROW_NUMBER() OVER (PARTITION BY cliente_id ORDER BY data DESC) AS rn
  FROM pedidos
)
SELECT * FROM ranked WHERE rn = 1;
```

## Tipos e cast

| Operação | Postgres | Snowflake | BigQuery | DuckDB |
|---|---|---|---|---|
| Cast | `valor::numeric` ou `CAST(valor AS numeric)` | `valor::NUMBER` ou `CAST` | `CAST(valor AS NUMERIC)` (`::` não suportado) | `valor::DOUBLE` ou `CAST` |
| JSON — extrair campo | `payload->>'campo'` | `payload:campo::string` | `JSON_EXTRACT_SCALAR(payload, '$.campo')` | `payload->>'campo'` |
| Array/lista literal | `ARRAY[1,2,3]` | `ARRAY_CONSTRUCT(1,2,3)` | `[1,2,3]` | `[1,2,3]` |

## Paginação com `LIMIT`/`OFFSET`

Sintaxe idêntica nos 4 engines (`LIMIT n OFFSET m`) — a diferença está no **custo**, não na
sintaxe. Ver `efficient-pagination.md` para por que `OFFSET` alto é caro em qualquer um deles.

## Gotchas de portabilidade

- BigQuery é **case-sensitive** para nomes de coluna por padrão em alguns contextos de
  `JSON_EXTRACT`; Postgres/Snowflake tendem a normalizar identificadores para minúsculo salvo
  aspas duplas — sempre teste identificadores com maiúscula ao portar.
- `NULL` em comparação: `NULL = NULL` é `NULL` (falso) em todos os 4 — use `IS NULL` /
  `IS NOT DISTINCT FROM` (Postgres/DuckDB) para comparação null-safe; Snowflake/BigQuery não
  têm `IS NOT DISTINCT FROM` padrão em todas as versões — verificar documentação da versão.
- `INTERVAL` como literal (`interval '7 days'`) é sintaxe Postgres/DuckDB — Snowflake e
  BigQuery preferem função (`DATEADD`/`DATE_ADD`) em vez de literal de intervalo solto.
- Ao portar CTE recursiva, ver `../concepts/cte-recursive-vs-materialized.md` — suporte e
  custo variam bastante entre engine transacional (Postgres) e MPP colunar (Snowflake/BigQuery).

## Referências
- `../concepts/window-functions.md` — semântica de `OVER()` (igual nos 4 engines, o que muda é `QUALIFY`)
- `../concepts/query-plan-reading.md` — comando de plano por engine
