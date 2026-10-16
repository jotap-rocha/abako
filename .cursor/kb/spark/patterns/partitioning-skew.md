---
topic: partitioning-skew
confidence: null
mcp_validated: null
---

# Particionamento e Prevenção de Data Skew

## Data skew — o que é

Uma ou poucas chaves concentram uma fração desproporcional dos dados (ex: 80% dos pedidos vêm de
1 `customer_id` de teste, ou um `country_code` nulo vira uma partição gigante). Na prática, isso
vira **1 task muito mais lenta que as outras** no mesmo stage — o job inteiro espera por ela.

## Diagnosticar antes de otimizar

```python
# 1. Ver na Spark UI: aba Stages → task com duração/registro muito acima da mediana

# 2. Confirmar a hipótese contando por chave
df.groupBy("customer_id").count().orderBy(desc("count")).show(10)

# 3. Confirmar AQE ligado (Spark 3.x+ já resolve boa parte automaticamente)
spark.conf.get("spark.sql.adaptive.skewJoin.enabled")  # deve ser "true"
```

## `repartition()` vs `coalesce()`

| Operação | Shuffle? | Uso |
|---|---|---|
| `repartition(n)` | Sim, sempre | Redistribuir uniformemente — use para resolver desbalanceamento antes de uma etapa cara |
| `repartition(n, "coluna")` | Sim | Redistribuir por chave (garante que a mesma chave cai na mesma partição) |
| `coalesce(n)` | Não (só reduz, sem shuffle) | Reduzir nº de partições antes de escrever (evita muitos arquivos pequenos) — mais barato que `repartition` |

```python
# Reduzir partições antes de escrever (barato, sem shuffle)
df.coalesce(10).write.parquet(output_path)

# Redistribuir uniformemente antes de uma operação cara (shuffle, mas resolve desbalanceamento)
df.repartition(200).groupBy("customer_id").agg(...)
```

`coalesce()` **não resolve skew** — ele só agrupa partições existentes, então se uma partição já
é gigante, `coalesce` não a divide. Para skew, use `repartition` ou salting.

## Salting — técnica manual para skew extremo

Quando AQE não resolve (ex: Spark < 3.x, ou skew tão extremo que mesmo com AQE 1 chave domina):

```python
from pyspark.sql.functions import concat, lit, rand, floor

N_SALTS = 20

# Lado esquerdo (grande, com skew): adiciona salt aleatório
salted_left = large_df.withColumn(
    "salted_key", concat(col("customer_id"), lit("_"), floor(rand() * N_SALTS))
)

# Lado direito (pequeno): explode em N_SALTS cópias, uma por valor de salt
salted_right = small_df.withColumn(
    "salt", explode(array([lit(i) for i in range(N_SALTS)]))
).withColumn("salted_key", concat(col("customer_id"), lit("_"), col("salt")))

result = salted_left.join(salted_right, "salted_key")
```

Isso distribui a chave dominante em `N_SALTS` sub-chaves, espalhando entre mais partições/tasks.

## AQE skew join — a alternativa preferida (Spark 3.x+)

```python
spark.conf.set("spark.sql.adaptive.enabled", "true")
spark.conf.set("spark.sql.adaptive.skewJoin.enabled", "true")
```

Com isso ligado, o Spark detecta partições desproporcionalmente grandes em runtime (com base em
`spark.sql.adaptive.skewJoin.skewedPartitionFactor` e `...skewedPartitionThresholdInBytes`) e as
divide automaticamente em sub-partições menores antes do join — elimina a necessidade de salting
manual na maioria dos casos.

## Gotchas

- Aumentar `spark.sql.shuffle.partitions` **não resolve skew** — se 1 chave domina o volume, ela
  continua caindo numa única partição não importa quantas partições existam no total.
- Nulos em chave de join/groupBy frequentemente causam skew "escondido" — todos os nulos caem na
  mesma partição. Trate nulos separadamente (`filter`/`coalesce` antes do join) se forem muitos.
- Salting exige lógica simétrica nos dois lados do join (explode do lado pequeno) — salting
  parcial (só de um lado) não funciona.
