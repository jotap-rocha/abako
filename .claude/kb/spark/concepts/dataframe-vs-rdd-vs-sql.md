---
topic: dataframe-vs-rdd-vs-sql
confidence: null
mcp_validated: null
---

# DataFrame vs RDD vs Spark SQL

## As três APIs, mesma engine

DataFrame, Dataset (Scala/Java) e Spark SQL compilam para o **mesmo plano físico** via Catalyst
optimizer — a escolha entre eles é de ergonomia, não de performance (quando bem escritos).
RDD é a camada de mais baixo nível e **não** passa pelo Catalyst nem pelo Tungsten.

| API | Otimizado por Catalyst? | Quando usar |
|---|---|---|
| RDD | Não | Só quando precisar de controle fino sobre particionamento/serialização que DataFrame não expõe, ou dados não-estruturados sem schema |
| DataFrame (PySpark) | Sim | Caso padrão — 95% do trabalho de engenharia de dados |
| Spark SQL (`spark.sql("...")`) | Sim | Quando a lógica é naturalmente SQL, ou para analistas/times que já pensam em SQL |

**Regra prática**: comece em DataFrame ou SQL. Só desça para RDD se tiver um motivo concreto
(ex: algoritmo customizado de particionamento, processamento de dados binários não tabulares).

## Catalyst optimizer

Pipeline de otimização do plano lógico antes de virar plano físico:

```
Unresolved Logical Plan
    → Analysis (resolve nomes de coluna/tabela contra o catálogo)
    → Logical Optimization (predicate pushdown, constant folding, column pruning)
    → Physical Planning (gera candidatos, escolhe pelo custo — ex: tipo de join)
    → Code Generation (Tungsten gera bytecode JVM otimizado)
```

Isso é o que permite ao Spark, por exemplo, aplicar um `.filter()` escrito depois de um `.join()`
*antes* do join de fato rodar (predicate pushdown) — porque o Catalyst só materializa o plano na
ação, não na declaração de cada transformação.

## Tungsten

Camada de execução que gerencia memória fora do heap Java (off-heap) e gera bytecode
especializado para cada operação, evitando overhead de serialização de objetos Java genéricos.
É o motivo de DataFrame/SQL serem consistentemente mais rápidos que RDD equivalente.

## UDFs quebram a otimização

```python
# RUIM — UDF Python é caixa-preta para o Catalyst, serializa linha a linha via Py4J
from pyspark.sql.functions import udf
@udf("double")
def to_fahrenheit(celsius):
    return celsius * 9/5 + 32
df.withColumn("f", to_fahrenheit(df.celsius))

# BOM — expressão nativa, permanece dentro do Tungsten, sem serialização Python
from pyspark.sql.functions import col
df.withColumn("f", col("celsius") * 9/5 + 32)
```

Se a lógica não existe como função nativa (`pyspark.sql.functions`), prefira **pandas UDF**
(vetorizada via Arrow) a UDF row-by-row — o custo de serialização cai drasticamente.

## Gotchas

- Dataset (API tipada) não existe em PySpark — é exclusivo de Scala/Java. Em Python, DataFrame já
  é a API de mais alto nível disponível.
- "SQL é mais lento que DataFrame" é mito — mesmo plano físico, mesma engine.
- RDD ainda aparece em código legado (Spark 1.x/2.x) — não é motivo para reescrever tudo, mas
  código novo não deveria começar em RDD sem justificativa.
