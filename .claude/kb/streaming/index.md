---
domain: streaming
description: Processamento de streaming — Kafka, Flink, CDC/Debezium: stream vs batch, watermarking, delivery semantics, particionamento, windowing, dedup, DLQ
mcp_validated: null
confidence: null
---

# KB: Streaming (Kafka, Flink, CDC)

Base de conhecimento de processamento de streaming para pipelines de dados em tempo real —
ingestão via CDC, agregação com janelas, garantias de entrega e tratamento de erro/atraso.

## Conceitos

| Arquivo | Tópico |
|---|---|
| [stream-vs-batch.md](concepts/stream-vs-batch.md) | Modelo de processamento contínuo vs bounded, quando usar cada um |
| [watermarking.md](concepts/watermarking.md) | Event time, watermark, dados atrasados |
| [delivery-semantics.md](concepts/delivery-semantics.md) | At-most-once / at-least-once / exactly-once |
| [kafka-partitioning.md](concepts/kafka-partitioning.md) | Partição, ordenação por key, consumer groups, hot partition |

## Padrões

| Arquivo | Tópico |
|---|---|
| [cdc-debezium.md](patterns/cdc-debezium.md) | CDC log-based de banco para stream, outbox pattern |
| [windowing.md](patterns/windowing.md) | Tumbling / sliding / session windows para agregação |
| [deduplication.md](patterns/deduplication.md) | Idempotência: chave natural, state store TTL, sink upsert |
| [dead-letter-queue.md](patterns/dead-letter-queue.md) | DLQ + retry topics para eventos com erro |

## Conformidade DE (ponte)

Fonte: `data-engineering.yaml` — este KB **não** duplica severidade nem texto normativo.

| Âncora | Relação |
|---|---|
| `DE-A*` | Universal |
| pacote **D** | se a tree for cloud |

## Learning path sugerido

1. `stream-vs-batch.md` — entender o modelo antes de qualquer implementação
2. `kafka-partitioning.md` — base de todo pipeline Kafka (ordenação, paralelismo)
3. `watermarking.md` + `windowing.md` — agregação correta em streaming
4. `delivery-semantics.md` + `deduplication.md` — garantir correção do dado
5. `cdc-debezium.md` — ingestão de banco para stream
6. `dead-letter-queue.md` — tratamento de erro em produção

## Capability map

| Preciso de... | Vou em... |
|---|---|
| Ingerir mudanças de um banco relacional como stream | `patterns/cdc-debezium.md` |
| Agregar eventos por janela de tempo | `patterns/windowing.md` + `concepts/watermarking.md` |
| Evitar processar o mesmo evento duas vezes | `patterns/deduplication.md` |
| Garantir que evento com erro não trava o pipeline | `patterns/dead-letter-queue.md` |
| Decidir se um problema é streaming ou batch | `concepts/stream-vs-batch.md` |
| Escolher número de partições de um tópico | `concepts/kafka-partitioning.md` |
| Escolher garantia de entrega (at-least-once etc.) | `concepts/delivery-semantics.md` |

## Quick Reference

Ver [quick-reference.md](quick-reference.md) — cheatsheet de semânticas de entrega, tipos de
janela e decision tree de tratamento de erro. Ler só se a tarefa exigir esse nível de detalhe.
