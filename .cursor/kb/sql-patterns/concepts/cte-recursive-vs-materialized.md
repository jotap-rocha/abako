---
topic: cte-recursive-vs-materialized
confidence: null
mcp_validated: null
---

# CTEs: Recursiva vs Materialização

## CTE recursiva — para dados hierárquicos/grafo

Resolve estruturas que `JOIN` normal não resolve: árvores de categoria, hierarquia de
funcionários, grafo de dependências, explosão de BOM (bill of materials).

```sql
-- Hierarquia de categorias (árvore) — Postgres/DuckDB/Snowflake/BigQuery (sintaxe similar)
WITH RECURSIVE categoria_tree AS (
  -- Caso base: raiz (sem pai)
  SELECT id, nome, parent_id, 1 AS nivel, nome::text AS caminho
  FROM categorias
  WHERE parent_id IS NULL

  UNION ALL

  -- Caso recursivo: junta com o resultado acumulado
  SELECT c.id, c.nome, c.parent_id, ct.nivel + 1, ct.caminho || ' > ' || c.nome
  FROM categorias c
  JOIN categoria_tree ct ON c.parent_id = ct.id
)
SELECT * FROM categoria_tree ORDER BY caminho;
```

### Anatomia
1. **Caso base** (âncora) — linhas iniciais, sem referência à própria CTE
2. **`UNION ALL`** — nunca `UNION` puro (dedup a cada iteração é caro; controle ciclo explicitamente se necessário)
3. **Caso recursivo** — referencia a CTE, junta com a próxima "camada"
4. Termina quando o caso recursivo não retorna mais linhas

### Guarda contra ciclo infinito (grafo com ciclo, não árvore garantida)

```sql
WITH RECURSIVE deps AS (
  SELECT id, parent_id, ARRAY[id] AS visited, 1 AS depth
  FROM nodes WHERE id = 'start'

  UNION ALL

  SELECT n.id, n.parent_id, d.visited || n.id, d.depth + 1
  FROM nodes n
  JOIN deps d ON n.parent_id = d.id
  WHERE NOT n.id = ANY(d.visited)   -- evita revisitar nó
    AND d.depth < 100               -- teto de segurança
)
SELECT * FROM deps;
```

## CTE materializada vs não-materializada (não-recursiva)

CTE comum (`WITH x AS (...)`) é um **fence de otimização** — o comportamento varia por engine
e versão:

| Engine | Comportamento default | Como forçar |
|---|---|---|
| Postgres ≥ 12 | **Inlined** (como subquery) se referenciada 1x e sem efeito colateral | `AS MATERIALIZED` / `AS NOT MATERIALIZED` |
| Postgres ≤ 11 | Sempre materializada (fence — otimizador não enxerga através) | não aplicável (comportamento fixo) |
| Snowflake | Otimizador decide (geralmente inline) | sem hint direto — reescrever como subquery/temp table se necessário |
| BigQuery | Otimizador decide (geralmente inline) | sem hint direto |
| DuckDB | Geralmente inline (CTE fusion) | `MATERIALIZED` (sintaxe suportada) |

```sql
-- Postgres 12+: força materializar (útil quando a CTE é cara e reusada, ou tem side-effect)
WITH stats AS MATERIALIZED (
  SELECT categoria_id, AVG(preco) AS preco_medio
  FROM produtos
  GROUP BY categoria_id
)
SELECT p.*, s.preco_medio
FROM produtos p
JOIN stats s ON s.categoria_id = p.categoria_id;

-- Postgres 12+: força NÃO materializar (deixa o planner empurrar predicados para dentro)
WITH recentes AS NOT MATERIALIZED (
  SELECT * FROM pedidos WHERE created_at > now() - interval '7 days'
)
SELECT * FROM recentes WHERE cliente_id = 42;
-- NOT MATERIALIZED permite ao planner reescrever como
-- "WHERE created_at > ... AND cliente_id = 42" e usar índice composto
```

## Quando materializar ajuda vs atrapalha

| Situação | Decisão |
|---|---|
| CTE referenciada 1x, com filtro que se beneficiaria de pushdown | `NOT MATERIALIZED` (ou deixe inline) |
| CTE referenciada N vezes (evita recomputar agregação cara) | `MATERIALIZED` |
| CTE recursiva | Sempre efetivamente materializada — é o mecanismo da recursão |
| CTE com função volátil (`random()`, `now()` em alguns casos) | `MATERIALIZED` — evita reavaliar por referência |

## Gotchas

- Antes de otimizar uma CTE, rode `query-plan-reading.md` — o plano mostra se ela foi inlined
  (aparece dissolvida dentro do plano) ou materializada (aparece como nó `CTE Scan`).
- CTE recursiva sem guarda de profundidade em dado com ciclo = loop até estourar memória/timeout.
- Em engines colunares (BigQuery/Snowflake), CTE recursiva geralmente tem suporte mais limitado
  ou custo mais alto que em Postgres — para hierarquias muito profundas, considere pré-computar
  o `caminho`/`nivel` em uma tabela materializada via pipeline em vez de recursão em tempo real.

## Referências
- `../patterns/slow-query-diagnosis.md` — passo 1 (ler o plano) mostra se a CTE virou fence
