---
topic: cluster-tuning
confidence: null
mcp_validated: null
---

# Tuning de Configuração de Cluster

## Regra de ouro: cores por executor, não cores totais

```
executor.cores muito alto (ex: 1 executor = todos os cores do node)
    → poucos executors grandes → menos paralelismo entre JVMs, GC pauses maiores,
      throughput de HDFS/shuffle degrada (contenção de I/O por executor)

executor.cores muito baixo (ex: 1 core por executor)
    → muitos executors pequenos → overhead de gerenciamento de tasks/broadcast
      cresce, cada executor tem pouca memória útil após overhead fixo
```

**Ponto de partida comum**: 4-5 cores por executor. Acima disso, throughput de HDFS/shuffle por
executor tende a degradar (contenção). É um ponto de partida, não uma regra fixa — meça.

## Dimensionar a partir do hardware do node

```
Exemplo: node com 16 cores, 64GB RAM

1. Reservar para o SO/daemons: ~1 core, ~1GB
   → disponível: 15 cores, 63GB

2. cores por executor = 5 (ponto de partida)
   → nº de executors por node = 15 / 5 = 3

3. memória por executor = 63GB / 3 = 21GB
   → reservar overhead do executor (spark.executor.memoryOverhead, default 10% ou mín. 384MB)
   → spark.executor.memory ≈ 19GB (deixando margem para overhead)

Resultado: spark.executor.cores=5, spark.executor.memory=19g, 3 executors/node
```

## `spark.executor.memoryOverhead`

Memória off-heap reservada para: overhead da JVM, estruturas nativas, e — em PySpark — parte da
comunicação com o processo Python. Default é `max(384MB, 0.10 * executor.memory)`. Se o job usa
UDFs Python pesados ou pandas UDF com dados grandes, considere subir explicitamente
(`spark.executor.memoryOverhead=2g` por exemplo) em vez de só aumentar `executor.memory`.

## `spark.sql.shuffle.partitions` — ajustar ao cluster, não deixar no default

```python
# Regra prática de partida: 2-3x o nº total de cores disponíveis no cluster
total_cores = n_executors * cores_per_executor
spark.conf.set("spark.sql.shuffle.partitions", total_cores * 2)
```

Com AQE ligado (`spark.sql.adaptive.enabled=true`), o Spark ajusta automaticamente o nº de
partições pós-shuffle via `coalescePartitions` — reduz (mas não elimina) a necessidade de acertar
esse valor manualmente. Ainda assim, um valor inicial razoável evita partições grandes demais
antes do AQE agir.

## Dynamic allocation — cluster elástico

```python
spark.conf.set("spark.dynamicAllocation.enabled", "true")
spark.conf.set("spark.dynamicAllocation.minExecutors", "2")
spark.conf.set("spark.dynamicAllocation.maxExecutors", "20")
spark.conf.set("spark.shuffle.service.enabled", "true")  # obrigatório para dynamic allocation
```

Deixa o Spark escalar nº de executors conforme a carga do job (útil em clusters compartilhados ou
managed, como Databricks/EMR/Dataproc, onde o custo de executor ocioso é real).

## Checklist antes de mexer em config de cluster

1. Rodou o job e olhou a Spark UI (Stages, Executors, SQL tab)? Sem isso, tuning é chute.
2. O gargalo é CPU, memória (spill/GC), ou shuffle (I/O de rede/disco)? Cada um pede ajuste
   diferente — mais cores não ajuda gargalo de I/O.
3. É skew (1 task lenta) ou volume real (todas as tasks lentas igualmente)? Ver
   [partitioning-skew.md](partitioning-skew.md) antes de aumentar recursos.
4. AQE está ligado? Antes de tuning manual extensivo, confirme que Spark 3.x+ já não resolveu boa
   parte automaticamente.

## Gotchas

- "Aumentar `executor.memory`" é o reflexo mais comum e raramente é a causa raiz — spill e OOM em
  geral vêm de skew ou de `shuffle.partitions` mal dimensionado, não de memória insuficiente por
  si só.
- Managed platforms (Databricks, EMR, Dataproc) frequentemente já aplicam defaults sensatos —
  revise o que a plataforma já configura antes de sobrescrever manualmente.
- `spark.executor.instances` é ignorado quando `dynamicAllocation.enabled=true` — não configure
  os dois juntos sem entender a precedência.
