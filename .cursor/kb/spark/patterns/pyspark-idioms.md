---
topic: pyspark-idioms
confidence: null
mcp_validated: null
---

# PySpark Idiomático para Transformações Comuns

## Use `pyspark.sql.functions`, não UDF

```python
from pyspark.sql import functions as F

# BOM — expressão nativa, otimizada pelo Catalyst/Tungsten
df.withColumn("full_name", F.concat_ws(" ", "first_name", "last_name"))
df.withColumn("year", F.year("created_at"))
df.withColumn("amount_usd", F.round(F.col("amount") * F.col("fx_rate"), 2))
df.withColumn("category", F.when(F.col("amount") > 1000, "high")
                            .when(F.col("amount") > 100, "medium")
                            .otherwise("low"))
```

Só recorra a UDF quando a lógica genuinamente não existe em `functions` — e prefira pandas UDF
(vetorizada) a UDF row-by-row nesse caso.

## Encadeamento de transformações — legível, sem `.collect()` no meio

```python
result = (
    df
    .filter(F.col("amount") > 0)
    .withColumn("month", F.date_trunc("month", "created_at"))
    .groupBy("month", "region")
    .agg(
        F.sum("amount").alias("total_amount"),
        F.count("*").alias("n_orders"),
        F.countDistinct("customer_id").alias("n_customers"),
    )
    .orderBy("month", "region")
)
```

## `select` com múltiplas colunas geradas — evite `withColumn` em loop

```python
# RUIM — cada withColumn em loop cria um novo plano lógico, degrada performance com muitas colunas
for c in numeric_cols:
    df = df.withColumn(f"{c}_scaled", F.col(c) / 100)

# BOM — uma única projeção
df = df.select(
    "*",
    *[(F.col(c) / 100).alias(f"{c}_scaled") for c in numeric_cols]
)
```

## Window functions em vez de self-join

```python
from pyspark.sql import Window

# Ranking / "top N por grupo" — window function, não self-join
w = Window.partitionBy("customer_id").orderBy(F.desc("order_date"))
df.withColumn("rn", F.row_number().over(w)).filter(F.col("rn") == 1)  # pedido mais recente por cliente

# Running total
w2 = Window.partitionBy("customer_id").orderBy("order_date") \
    .rowsBetween(Window.unboundedPreceding, Window.currentRow)
df.withColumn("running_total", F.sum("amount").over(w2))
```

## Deduplicação idiomática

```python
# Manter só a última versão por chave (ex: SCD / late-arriving updates)
w = Window.partitionBy("id").orderBy(F.desc("updated_at"))
deduped = df.withColumn("rn", F.row_number().over(w)) \
    .filter(F.col("rn") == 1).drop("rn")

# Deduplicação simples (linha idêntica repetida)
df.dropDuplicates(["id"])   # mantém 1 arbitrária por chave, não necessariamente a mais recente
```

## pandas UDF quando UDF é inevitável

```python
import pandas as pd
from pyspark.sql.functions import pandas_udf

@pandas_udf("double")
def normalize(s: pd.Series) -> pd.Series:
    return (s - s.mean()) / s.std()

df.withColumn("amount_norm", normalize("amount"))
```

Vetorizado via Apache Arrow — ordens de magnitude mais rápido que UDF row-by-row para lógica que
não tem equivalente nativo (ex: chamada a biblioteca científica Python).

## Gotchas

- `.toPandas()` traz todo o DataFrame para o driver — mesmo risco de `.collect()`. Só use em
  resultados já agregados/pequenos.
- `F.col("coluna")` vs string `"coluna"` — a maioria das funções aceita ambos, mas em expressões
  compostas (`F.col("a") + F.col("b")`) o `F.col()` explícito é obrigatório.
- `dropDuplicates()` sem lista de colunas compara **todas** as colunas — raramente é a intenção;
  quase sempre se quer deduplicar por uma chave de negócio específica.
- Encadear muitos `.withColumn()` funciona, mas para dezenas de colunas geradas dinamicamente,
  `.select()` com lista de expressões é mais legível e mais barato para o planner.
