---
topic: lazy-evaluation
confidence: null
mcp_validated: null
---

# Lazy Evaluation e Planos de Execução

## Transformações vs Ações

- **Transformação** (`.filter()`, `.select()`, `.join()`, `.groupBy()`...): retorna um novo
  DataFrame, mas **não executa nada** — só registra a operação no plano lógico.
- **Ação** (`.collect()`, `.count()`, `.write()`, `.show()`, `.take()`...): dispara a execução
  real de todo o plano acumulado até ali.

```python
df2 = df.filter(col("amount") > 0)     # nada executa ainda
df3 = df2.withColumn("tax", col("amount") * 0.1)  # ainda nada
df3.write.saveAsTable("silver.orders")  # AQUI todo o plano roda de uma vez
```

## Por que isso importa

O Spark só otimiza (Catalyst) o plano **completo** na hora da ação — por isso consegue fazer
predicate pushdown, column pruning e reordenar operações mesmo que o código as declare em outra
ordem. Escrever várias transformações antes de uma ação não é "processar em etapas" — é montar
um plano que roda de uma vez, otimizado como um todo.

## Os 4 planos (pipeline de `explain()`)

```
Parsed Logical Plan       → parse do código, sem validação
Analyzed Logical Plan     → resolve nomes de coluna/tabela contra o catálogo
Optimized Logical Plan    → Catalyst aplica predicate pushdown, column pruning etc.
Physical Plan             → escolhe algoritmo concreto (ex: BroadcastHashJoin vs SortMergeJoin)
```

```python
df.explain(mode="formatted")   # plano físico legível, com stages numerados
df.explain(True)               # todos os 4 planos (parsed → physical)
```

## Lendo um physical plan — o que procurar

```
== Physical Plan ==
* BroadcastHashJoin [customer_id], [customer_id], Inner, BuildRight
  :- * Filter (amount > 0)
  :  +- * FileScan parquet orders
  +- BroadcastExchange
     +- FileScan parquet customers
```

- `BroadcastHashJoin` / `SortMergeJoin` — qual estratégia de join foi escolhida (ver
  [join-optimization.md](../patterns/join-optimization.md))
- `Exchange` — marca um shuffle boundary (novo stage)
- `Filter`/`Project` antes do `Scan` — sinal de que predicate/column pushdown funcionou
- `PushedFilters` no `FileScan` — filtro empurrado até a leitura do arquivo (Parquet/Delta)

## `.cache()` / `.persist()` quebram parte da lazy chain

```python
df_cached = df.filter(col("amount") > 0).cache()
df_cached.count()          # ação dispara o cálculo E materializa o cache
df_cached.groupBy("id").count()   # reusa o resultado cacheado, não recalcula o filter
```

Use quando o mesmo DataFrame intermediário é reusado em múltiplas ações — sem cache, cada ação
reexecuta a lazy chain inteira desde a fonte.

## Gotchas

- Chamar `.count()` só para "ver quantas linhas tem" no meio do pipeline dispara uma execução
  completa e cara — se for só debug, use `.explain()` ou `df.limit(5).show()`.
- `.cache()` sem uma ação em seguida não materializa nada — cache também é lazy.
- Cache "esquecido" (não liberado com `.unpersist()`) consome memória do executor ao longo de um
  job longo — libere quando não precisar mais.
