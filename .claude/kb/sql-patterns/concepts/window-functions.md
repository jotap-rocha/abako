---
topic: window-functions
confidence: null
mcp_validated: null
---

# Window Functions

## Conceito

`OVER()` calcula um valor por linha considerando um conjunto ("janela") de linhas relacionadas,
sem colapsar o resultado como `GROUP BY` faz. A linha original é preservada.

```sql
SELECT
  pedido_id,
  cliente_id,
  valor,
  SUM(valor) OVER (PARTITION BY cliente_id) AS total_cliente,
  RANK() OVER (PARTITION BY cliente_id ORDER BY valor DESC) AS rank_valor
FROM pedidos;
```

## Anatomia: `PARTITION BY` + `ORDER BY` + frame

```sql
funcao() OVER (
  PARTITION BY coluna       -- agrupa a janela (opcional — sem isso, janela = tabela inteira)
  ORDER BY coluna            -- ordena dentro da partição (necessário p/ funções de ranking/lag)
  ROWS BETWEEN N PRECEDING AND CURRENT ROW  -- frame explícito (opcional)
)
```

- **Sem `ORDER BY`**: frame default = partição inteira. `SUM`/`AVG`/`COUNT` agregam tudo.
- **Com `ORDER BY`** (sem frame explícito): frame default = `RANGE BETWEEN UNBOUNDED PRECEDING
  AND CURRENT ROW` — soma acumulada até a linha atual (running total).

## Quando substitui self-join / subquery correlacionada

| Necessidade | Sem window function | Com window function |
|---|---|---|
| "Top N por grupo" | Self-join + `GROUP BY` + `HAVING` | `RANK() OVER (PARTITION BY grupo ORDER BY valor DESC)` |
| "% do total do grupo" | Subquery correlacionada por linha | `valor / SUM(valor) OVER (PARTITION BY grupo)` |
| "Valor da linha anterior" | Self-join com `id - 1` (frágil) | `LAG(valor) OVER (ORDER BY data)` |
| "Running total" | Subquery correlacionada `O(n²)` | `SUM(valor) OVER (ORDER BY data)` |

Subquery correlacionada roda uma vez **por linha externa** (`O(n²)` na prática) — window
function calcula em uma passada ordenada (`O(n log n)`, geralmente um único `Sort` no plano).

## Funções mais usadas

```sql
-- Ranking (comportamento diferente com empate)
ROW_NUMBER() OVER (...)  -- sempre único: 1,2,3,4
RANK()       OVER (...)  -- empate compartilha posição, pula a próxima: 1,2,2,4
DENSE_RANK() OVER (...)  -- empate compartilha posição, não pula: 1,2,2,3

-- Navegação
LAG(valor, 1)  OVER (ORDER BY data)   -- valor da linha anterior
LEAD(valor, 1) OVER (ORDER BY data)   -- valor da próxima linha
FIRST_VALUE(valor) OVER (...)
LAST_VALUE(valor)  OVER (... ROWS BETWEEN UNBOUNDED PRECEDING AND UNBOUNDED FOLLOWING)

-- Agregação como window
SUM(valor)   OVER (PARTITION BY cliente_id ORDER BY data)  -- running total
AVG(valor)   OVER (ORDER BY data ROWS BETWEEN 6 PRECEDING AND CURRENT ROW)  -- média móvel 7 linhas
```

## Padrão: deduplicar mantendo a linha "mais recente"

```sql
-- Manter só o registro mais recente por cliente_id
WITH ranked AS (
  SELECT *, ROW_NUMBER() OVER (PARTITION BY cliente_id ORDER BY updated_at DESC) AS rn
  FROM clientes_staging
)
SELECT * FROM ranked WHERE rn = 1;
```

## Custo no plano

Window function tipicamente gera um nó `WindowAgg` (Postgres) precedido de `Sort` pela
`PARTITION BY`/`ORDER BY` — se já existir índice cobrindo essas colunas na mesma ordem, o
`Sort` pode ser evitado (`Index Scan` já entrega ordenado).

## Gotchas

- `WHERE` **não pode** filtrar o resultado de uma window function (ela roda depois do `WHERE`
  na ordem lógica de execução do SQL) — use subquery/CTE + filtro externo, ou `QUALIFY`
  (Snowflake, BigQuery, DuckDB — não existe em Postgres).
- Múltiplas window functions com `PARTITION BY`/`ORDER BY` diferentes geram múltiplos `Sort` —
  agrupe em uma única especificação de janela (`WINDOW w AS (...)`) quando possível.
- `LAST_VALUE` sem frame explícito surpreende: o default `RANGE ... CURRENT ROW` faz com que
  ele retorne a própria linha atual, não a última da partição — sempre declare o frame.

## Referências
- `../patterns/slow-query-diagnosis.md` — como identificar `Sort`/`WindowAgg` caro no plano
