---
topic: join-optimization
confidence: null
mcp_validated: null
---

# Otimização de Joins — Broadcast vs Shuffle

## Os dois algoritmos principais

| Estratégia | Como funciona | Custo | Quando o Spark escolhe |
|---|---|---|---|
| **Broadcast Hash Join** | Copia a tabela pequena inteira para todos os executors; cada partição da tabela grande é filtrada localmente, sem shuffle | Sem shuffle da tabela grande — muito mais rápido | Uma das tabelas é menor que `spark.sql.autoBroadcastJoinThreshold` (default 10MB) |
| **Sort-Merge Join** | Ambas as tabelas são particionadas (shuffle) pela chave de join, ordenadas, e mescladas partição a partição | Shuffle de ambos os lados — caro em rede/disco | Ambas as tabelas são grandes demais para broadcast |

## Broadcast join — forçar explicitamente

```python
from pyspark.sql.functions import broadcast

# Tabela de dimensão pequena (ex: catálogo de produtos, lista de países)
result = orders_df.join(broadcast(products_df), "product_id")
```

Use `broadcast()` explícito quando:
- A tabela é pequena mas o Spark não detectou automaticamente (estatísticas do catálogo
  desatualizadas, ou a tabela vem de uma transformação complexa sem estatística confiável)
- Você quer garantir o comportamento independente de `autoBroadcastJoinThreshold`

**Cuidado**: broadcast de uma tabela grande demais estoura a memória do executor (cada executor
recebe uma cópia completa). Se não tem certeza do tamanho, deixe o AQE decidir dinamicamente.

## AQE (Adaptive Query Execution) — deixar o Spark decidir em runtime

Desde Spark 3.x, com `spark.sql.adaptive.enabled=true` (default), o Spark pode **trocar** um
sort-merge join por broadcast join em runtime, depois de ver o tamanho real dos dados após
filtros — mesmo que a estimativa inicial do otimizador estivesse errada.

```python
spark.conf.set("spark.sql.adaptive.enabled", "true")  # já é default em 3.x+
```

Isso reduz muito a necessidade de `broadcast()` manual — mas não elimina: para pipelines com
tabelas de tamanho previsível e estável, `broadcast()` explícito ainda documenta a intenção e
evita depender de heurística.

## Subir o threshold de broadcast automático

```python
spark.conf.set("spark.sql.autoBroadcastJoinThreshold", 50 * 1024 * 1024)  # 50MB
```

Só suba se souber que a tabela pequena cabe confortavelmente na memória de cada executor
multiplicado pelo nº de executors que vão recebê-la simultaneamente.

## Evitar shuffle join desnecessário: bucketing (tabelas persistidas)

Para joins repetidos na mesma chave, entre tabelas grandes que não cabem em broadcast, bucketing
evita reshuffle a cada execução:

```python
df.write.bucketBy(200, "customer_id").sortBy("customer_id") \
    .saveAsTable("silver.orders_bucketed")
```

Ambas as tabelas do join precisam estar bucketed pela **mesma chave e mesmo número de buckets**
para o Spark pular o shuffle nesse join.

## Gotchas

- Join entre duas tabelas grandes sem broadcast nem bucketing = shuffle join sempre, mesmo que a
  chave de join tenha baixa cardinalidade — não existe "join rápido" nesse cenário sem
  pré-otimização.
- `broadcast()` em uma tabela que na verdade é grande (ex: cresceu desde a última vez que foi
  medida) causa OOM no executor — não silenciosamente lento, quebra.
- Full outer join e joins com condição não-equality (`<`, `>`, `BETWEEN`) não se beneficiam de
  broadcast hash join da mesma forma — verifique o physical plan (`explain()`) para confirmar
  qual estratégia foi de fato escolhida, não assuma.
