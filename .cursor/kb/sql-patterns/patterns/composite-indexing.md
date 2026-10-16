---
topic: composite-indexing
confidence: null
mcp_validated: null
---

# Estratégia de Indexação Composta

## Regra de ordem: seletividade + padrão de uso, não só cardinalidade

Ordem das colunas em `CREATE INDEX (a, b, c)` importa — o índice só é usado eficientemente
para predicados que respeitam o prefixo esquerdo (como um índice de livro: útil por
"capítulo, seção", inútil se você só sabe a "seção").

```sql
CREATE INDEX idx_pedidos_tenant_status ON pedidos (tenant_id, status, created_at);

-- Usa o índice completo (prefixo tenant_id, status, e created_at para ordenação/range):
WHERE tenant_id = $1 AND status = $2 ORDER BY created_at DESC

-- Usa só o prefixo (tenant_id) — ainda ajuda, mas não filtra por status via índice:
WHERE tenant_id = $1

-- NÃO usa o índice para o predicado de status (quebra o prefixo esquerdo):
WHERE status = $2   -- sem tenant_id, o planner ignora este índice
```

### Ordem recomendada quando não há caso de uso dominante único

1. Coluna de **igualdade mais seletiva primeiro** (reduz mais linhas por comparação exata).
2. Colunas de **igualdade adicionais** depois, na ordem de uso mais comum.
3. Coluna de **range/ordenação** (`created_at`, `preco > X`) por último — range quebra o
   "aproveitamento" de igualdade nas colunas seguintes, então deve vir ao final.

```sql
-- Predicado: tenant_id = ? AND status = ? AND created_at > ?
-- Ordem certa: igualdade, igualdade, range
CREATE INDEX idx_pedidos ON pedidos (tenant_id, status, created_at);

-- Ordem errada: range no meio quebra uso de status como filtro de índice
CREATE INDEX idx_pedidos_errado ON pedidos (tenant_id, created_at, status);
```

## Index-only scan (evitar heap fetch)

Se o índice contém **todas** as colunas que a query pede (no `SELECT`, `WHERE`, `ORDER BY`),
o engine não precisa ir buscar a linha na tabela — resolve tudo lendo só o índice.

```sql
-- Query
SELECT status, created_at FROM pedidos WHERE tenant_id = $1 AND status = $2;

-- Índice que habilita Index Only Scan (Postgres): inclui as colunas do SELECT
CREATE INDEX idx_pedidos_covering ON pedidos (tenant_id, status) INCLUDE (created_at);
-- INCLUDE adiciona colunas ao índice sem torná-las parte da chave de busca/ordenação —
-- só para "cobrir" o SELECT e evitar heap fetch.
```

No plano, o sinal é `Index Only Scan` em vez de `Index Scan` — este último ainda faz um
fetch extra na tabela ("heap fetch") por linha encontrada.

## Índice parcial — quando o filtro é sempre o mesmo valor

```sql
-- Se 95% das queries filtram "ativo = true", indexar só essas linhas é menor e mais rápido
CREATE INDEX idx_produtos_ativos ON produtos (categoria_id) WHERE ativo = true;

-- A query PRECISA ter o mesmo predicado no WHERE para o planner considerar o índice parcial:
SELECT * FROM produtos WHERE categoria_id = $1 AND ativo = true;  -- usa o índice parcial
SELECT * FROM produtos WHERE categoria_id = $1;                    -- NÃO usa (falta ativo=true)
```

Vantagem: índice menor (só as linhas relevantes), mais rápido de manter e de ler.

## Índice de expressão — quando o filtro usa função

```sql
-- Query com função na coluna nunca usa índice comum:
WHERE LOWER(email) = 'user@example.com'

-- Índice de expressão resolve:
CREATE INDEX idx_produtos_email_lower ON produtos (LOWER(email));
```

## Trade-off: cada índice custa escrita

Todo índice adicional é mantido em cada `INSERT`/`UPDATE`/`DELETE` que toca a coluna indexada.
Antes de criar um índice novo:

1. Verifique se já existe um índice cujo **prefixo** já cobre o caso (não duplique).
2. Meça o ganho de leitura (`EXPLAIN ANALYZE` antes/depois) contra o custo de escrita esperado
   (tabela com alta frequência de `INSERT` sofre mais com índices extras).
3. Prefira `CREATE INDEX CONCURRENTLY` (Postgres) em produção — evita lock exclusivo na tabela
   durante a criação.

```sql
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_pedidos_tenant_status
  ON pedidos (tenant_id, status, created_at);
```

## Cross-engine: o que muda

| Conceito | Postgres | Snowflake | BigQuery | DuckDB |
|---|---|---|---|---|
| Índice tradicional (B-tree) | Sim | Não (usa micro-partitions + pruning) | Não (usa particionamento/clustering) | Sim |
| Equivalente a "índice" | `CREATE INDEX` | Clustering key (`ALTER TABLE ... CLUSTER BY`) | Partição + clustering de tabela | `CREATE INDEX` |
| Índice parcial | `WHERE` no `CREATE INDEX` | Não aplicável (sem índice tradicional) | Não aplicável | Suportado |
| Index-only scan | Sim (`INCLUDE`) | Conceito não aplicável (colunar já evita ler colunas não usadas) | Conceito não aplicável (colunar) | Sim |

Em Snowflake/BigQuery, o ganho equivalente a "índice composto bem ordenado" vem de
**clustering key**/**particionamento** alinhado ao padrão de filtro mais comum (geralmente
`tenant_id`/data) — o princípio de "coluna mais seletiva/mais usada primeiro" se aplica
igualmente à escolha da clustering key.

## Referências
- `../concepts/join-types-costs.md` — como índice composto habilita nested loop/merge join eficiente
- `efficient-pagination.md` — índice composto que sustenta keyset pagination
- `slow-query-diagnosis.md` — passo 4, quando criar índice é a ação certa
