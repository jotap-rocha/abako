---
domain: spark
description: Apache Spark — modelo de execução distribuída, DataFrame/RDD/SQL, lazy evaluation, tuning de cluster
mcp_validated: null
confidence: null
---

# KB: Apache Spark

Base de conhecimento de Apache Spark para engenharia de dados distribuída: modelo de execução,
otimização de joins, particionamento e tuning de cluster. Princípio central: **entender o plano
de execução antes de otimizar** — a maioria dos problemas de performance em Spark é join mal
escolhido, skew não tratado, ou configuração de executor genérica demais para a carga real.

## Conformidade DE (ponte)

Fonte: `data-engineering.yaml` — este KB **não** duplica severidade nem texto normativo.

| Âncora | Relação |
|---|---|
| `DE-A*` | Universal |
| pacote **B** (`DE-B*`) | jobs Spark / YARN |

## Conceitos

| Arquivo | Tópico |
|---|---|
| [execution-model.md](concepts/execution-model.md) | Partições, stages, shuffle — como o Spark distribui trabalho |
| [dataframe-vs-rdd-vs-sql.md](concepts/dataframe-vs-rdd-vs-sql.md) | Quando usar cada API, Catalyst optimizer, Tungsten |
| [lazy-evaluation.md](concepts/lazy-evaluation.md) | Transformações vs ações, logical/physical plan, `explain()` |
| [memory-management.md](concepts/memory-management.md) | Unified memory (storage vs execution), spill para disco |

## Padrões

| Arquivo | Tópico |
|---|---|
| [join-optimization.md](patterns/join-optimization.md) | Broadcast join vs shuffle (sort-merge) join, quando forçar cada um |
| [partitioning-skew.md](patterns/partitioning-skew.md) | `repartition`/`coalesce`, salting, AQE skew join |
| [pyspark-idioms.md](patterns/pyspark-idioms.md) | Transformações idiomáticas, o que evitar (UDF, `collect()`, loops) |
| [cluster-tuning.md](patterns/cluster-tuning.md) | executor cores/memory, `spark.sql.shuffle.partitions`, AQE |

## Quick Reference

Ver [quick-reference.md](quick-reference.md) — cheatsheet de configs, decision tree de join e
checklist de diagnóstico de skew. Ler só se a tarefa exigir esse nível de detalhe operacional.

## Nota de validação

Este domínio foi criado **sem acesso ao Context-7 MCP** nesta sessão (ferramenta não disponível
no ambiente de execução). O conteúdo reflete conhecimento estável e amplamente documentado do
Spark (APIs e comportamento de execução não mudam com frequência entre minor versions), mas
`mcp_validated`/`confidence` ficam `null` até uma auditoria real via Context-7 — não invente
esses valores. Rode o Modo 2 (auditoria) deste skill assim que o MCP estiver disponível.
