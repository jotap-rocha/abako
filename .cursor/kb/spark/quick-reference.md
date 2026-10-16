---
domain: spark
topic: quick-reference
---

# Apache Spark — Quick Reference

### Configs mais usadas

| Config | Default | Quando mexer |
|---|---|---|
| `spark.sql.shuffle.partitions` | 200 | Ajustar para ~2-3x nº de cores do cluster; 200 é genérico demais para clusters pequenos ou grandes |
| `spark.sql.autoBroadcastJoinThreshold` | 10MB | Subir se a tabela pequena do join for maior que 10MB e couber em memória do executor |
| `spark.sql.adaptive.enabled` | true (3.x+) | Manter ligado — habilita AQE (coalesce partitions, skew join, broadcast dinâmico) |
| `spark.sql.adaptive.skewJoin.enabled` | true (3.x+) | Manter ligado se há suspeita de skew |
| `spark.executor.memory` | cluster-dependent | Ver [cluster-tuning.md](patterns/cluster-tuning.md) |
| `spark.executor.cores` | cluster-dependent | 4-5 cores por executor é o ponto ótimo comum (mais que isso degrada I/O do HDFS/shuffle) |

### Decision tree: qual tipo de join?

```
Uma das tabelas é pequena (< ~10MB, ou cabe confortavelmente em memória)?
    ├── SIM → broadcast join (broadcast() explícito, ou deixar AQE decidir)
    └── NÃO → ambas grandes?
        ├── Chave de join tem poucos valores dominando o volume (skew)?
        │   └── SIM → salting, ou AQE skewJoin.enabled=true
        │   └── NÃO → shuffle (sort-merge) join padrão — sem ação
```

### Checklist de diagnóstico de skew

1. Olhe a Spark UI → aba Stages → task com duração muito maior que as demais (outlier)
2. Olhe `df.groupBy(join_key).count().orderBy(desc("count"))` — um valor domina o volume?
3. Confirme AQE ligado (`spark.sql.adaptive.skewJoin.enabled=true`) antes de otimizar manualmente
4. Se AQE não resolver: salting na chave, ou split do dataset (skewed rows separadas)

### O que NUNCA fazer em PySpark

- `df.collect()` em DataFrame grande — traz tudo para o driver, estoura memória
- UDF Python quando existe função nativa equivalente (`pyspark.sql.functions`) — UDF Python
  serializa linha a linha via Py4J, perde otimização do Catalyst/Tungsten
- Loop Python chamando `.filter()`/`.union()` repetidamente em vez de uma transformação vetorizada
- `repartition()` sem necessidade antes de um `write` — geralmente `coalesce()` basta e é mais barato

### Ler o plano antes de otimizar

```python
df.explain(mode="formatted")   # physical plan legível, com stages
df.explain(mode="cost")        # inclui estimativas de custo do Catalyst
```

Ver [lazy-evaluation.md](concepts/lazy-evaluation.md) para como interpretar o plano.
