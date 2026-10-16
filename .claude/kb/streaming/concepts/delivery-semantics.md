# Semânticas de Entrega — At-Most-Once, At-Least-Once, Exactly-Once

## As 3 garantias

| Semântica | Garantia | Risco |
|---|---|---|
| **At-most-once** | Mensagem entregue 0 ou 1 vez | Perda de dados (sem retry após falha) |
| **At-least-once** | Mensagem entregue 1 ou mais vezes | Duplicatas (retry reenviando o que já processou) |
| **Exactly-once** | Mensagem entregue exatamente 1 vez, efeito líquido | Mais caro, requer coordenação (2PC/transações) |

Não existe "exactly-once" de graça — é sempre **at-least-once + deduplicação** (idempotência) ou
**transações distribuídas** (produtor + consumidor no mesmo commit atômico).

## Kafka producer: idempotência

```python
from kafka import KafkaProducer

producer = KafkaProducer(
    bootstrap_servers="kafka:9092",
    enable_idempotence=True,   # evita duplicatas em retry do PRODUTOR
    acks="all",                # espera confirmação de todas as réplicas in-sync
    retries=5,
)
```

`enable_idempotence=True` resolve duplicação causada por retry do produtor (rede instável),
mas **não** resolve duplicação end-to-end (produtor → processamento → sink).

## Kafka producer: transações (exactly-once entre tópicos)

```python
producer = KafkaProducer(
    bootstrap_servers="kafka:9092",
    transactional_id="orders-processor-1",
    enable_idempotence=True,
)
producer.init_transactions()

try:
    producer.begin_transaction()
    producer.send("orders-processed", value=processed_event)
    producer.send("orders-audit", value=audit_event)
    producer.commit_transaction()   # atômico: ambos ou nenhum
except Exception:
    producer.abort_transaction()
    raise
```

## Consumer: estratégias de commit de offset

| Estratégia | Quando o offset é commitado | Semântica resultante |
|---|---|---|
| Auto-commit (`enable.auto.commit=true`) | Periodicamente, independente de processar com sucesso | At-most-once (risco de perda se crash entre commit e processar) |
| Commit após processar (manual) | Depois que o efeito colateral (write no sink) foi feito | At-least-once (reprocessa se crash entre write e commit) |
| Commit + write atômico (transacional) | Offset e write no sink no mesmo commit | Exactly-once (Kafka Streams EOS, Flink checkpoint + 2PC sink) |

```python
# At-least-once: commit manual DEPOIS de garantir o efeito colateral
consumer = KafkaConsumer(
    "orders", bootstrap_servers="kafka:9092",
    enable_auto_commit=False,
    group_id="orders-processor",
)
for msg in consumer:
    process_and_write_to_sink(msg.value)   # efeito colateral primeiro
    consumer.commit()                       # só commita depois de garantir a escrita
```

## Exactly-once end-to-end (Kafka Streams / Flink)

```java
// Kafka Streams: EOS v2 — transação cobre read + process + write
props.put(StreamsConfig.PROCESSING_GUARANTEE_CONFIG, StreamsConfig.EXACTLY_ONCE_V2);
```

```java
// Flink: checkpoint + two-phase commit sink (ex: Kafka sink transacional)
env.enableCheckpointing(60000); // checkpoint a cada 60s
env.setStateBackend(new EmbeddedRocksDBStateBackend());
```

Exactly-once real end-to-end exige que **sink, processamento e checkpoint** estejam todos sob a
mesma coordenação transacional. Um sink não-transacional (ex.: HTTP externo, S3 sem staging)
quebra a garantia mesmo que o resto do pipeline seja exactly-once.

## Escolhendo a semântica

```
Dado precisa ser 100% correto (dinheiro, fraude, auditoria)?
    └── SIM → exactly-once (transações + sink idempotente/transacional)
    └── NÃO
        └── Duplicata é tolerável no consumidor (idempotente por design)?
            └── SIM → at-least-once (mais simples, mais barato, mais comum)
            └── NÃO, e perda é tolerável (métricas, logs) → at-most-once
```

## Gotchas

- **"Exactly-once" do Kafka Streams não cobre side-effects externos** — se o processador chama
  uma API externa não-idempotente dentro do processamento, ainda pode duplicar a chamada em
  reprocessamento.
- **At-least-once é o padrão de fato na maioria dos pipelines de produção** — combine com
  deduplicação no consumidor (ver `../patterns/deduplication.md`) em vez de forçar exactly-once
  em todo o pipeline, que é mais caro e mais frágil.
- **Auto-commit não é "mais seguro por padrão"** — é at-most-once, o pior caso de perda. Prefira
  desligar e commitar manualmente após o efeito colateral.

## Referências
- `../patterns/deduplication.md` — como implementar idempotência no consumidor
- `kafka-partitioning.md` — ordenação dentro da partição afeta como retries se comportam
