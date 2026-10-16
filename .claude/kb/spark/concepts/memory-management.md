---
topic: memory-management
confidence: null
mcp_validated: null
---

# Gerenciamento de Memória do Executor

## Unified Memory Manager (Spark 1.6+)

A memória JVM de cada executor (`spark.executor.memory`) é dividida assim:

```
Memória do executor (spark.executor.memory)
├── Reserved Memory (~300MB fixo, overhead interno do Spark)
└── Resto (spark.memory.fraction, default 0.6)
    ├── Storage Memory   → cache de DataFrames (.cache()/.persist()), broadcast variables
    └── Execution Memory → shuffles, joins, aggregations, sorts
```

- **Unified**: storage e execution **compartilham** o mesmo pool e podem tomar memória um do
  outro dinamicamente (`spark.memory.storageFraction` define o mínimo protegido para storage,
  default 0.5 do pool unificado).
- Se execution precisa de mais memória (ex: um shuffle grande), pode desalojar blocos de storage
  cacheados (evict) — exceto os que estão marcados como pinned durante uso ativo.
- Fora desse pool unificado, sobra memória para: estruturas internas do usuário/objetos Python
  (via Py4J), e — em PySpark — a memória do **processo Python separado** (ver abaixo).

## PySpark tem 2 processos de memória por executor

```
JVM do executor (spark.executor.memory)
    ↔ (serialização Arrow/Py4J)
Processo Python worker (spark.executor.pyspark.memory, opcional)
```

- Toda vez que o código Python roda algo que a JVM não executa nativamente (UDF Python, RDD com
  `.map()` em objeto Python, pandas UDF), os dados cruzam a fronteira JVM↔Python.
- `spark.executor.pyspark.memory` limita a memória do processo Python separadamente da JVM — sem
  isso configurado, um UDF Python com vazamento de memória pode estourar o memory limit do
  container/node sem o Spark "ver" isso como pressão de memória da JVM.

## Spill para disco

Quando execution memory não é suficiente para uma operação (ex: shuffle de um dataset grande, ou
um `sort` grande), o Spark **derrama (spills)** dados intermediários para disco local do
executor, em vez de estourar OutOfMemory. Isso funciona, mas é lento (I/O de disco).

Sinais de spill excessivo na Spark UI (aba Stages → detalhe da task):
- `Spill (Memory)` / `Spill (Disk)` com valores altos
- Tasks muito mais lentas que o esperado para o volume de dados

## Gotchas

- `spark.executor.memory` alto não elimina spill se a causa é **skew** (1 partição gigante) — a
  solução é reparticionar/salting, não só dar mais memória.
- `.cache()` de um DataFrame maior que a storage memory disponível causa eviction parcial —
  partes do cache são recalculadas quando acessadas de novo, silenciosamente.
- Memória "off-heap" (`spark.memory.offHeap.enabled`) existe e evita GC pauses da JVM, mas raro
  ser necessário fora de cargas muito grandes — não ativar sem medir o problema primeiro.
- Ver [cluster-tuning.md](../patterns/cluster-tuning.md) para como dimensionar
  `spark.executor.memory`/`cores` juntos (memória por core, não só memória total).
