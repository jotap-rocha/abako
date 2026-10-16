# Deduplicação de Eventos

## Por que duplicatas acontecem

At-least-once (o padrão de fato na maioria dos pipelines, ver
`../concepts/delivery-semantics.md`) garante que nenhum evento é perdido — ao custo de permitir
duplicatas em retry: producer retry, consumer rebalance no meio do processamento, restart de
connector CDC (Debezium reenvia desde o último offset commitado), reprocessamento manual.

## Estratégia 1 — chave de idempotência natural

Se o evento já tem um identificador único de negócio (order_id, transaction_id, ou
`(aggregate_id, event_type, version)` no outbox pattern), use-o como chave de dedup.

```python
# CDC: (table, primary_key, source.lsn) é único por mudança real no Postgres
def dedup_key(event: dict) -> str:
    return f"{event['source']['table']}:{event['after']['id']}:{event['source']['lsn']}"
```

## Estratégia 2 — state store com janela de TTL

Manter um set/map de chaves já processadas, com expiração — não é possível guardar tudo para
sempre, mas duplicatas em streaming tipicamente chegam dentro de uma janela curta (segundos a
minutos após o restart/retry).

```java
// Kafka Streams: state store para dedup com TTL implícito via janela
KeyValueStore<String, Long> seenStore = ...; // dedup-store, com retenção configurada

stream.transformValues(() -> new ValueTransformerWithKey<String, Order, Order>() {
    @Override
    public Order transform(String key, Order order) {
        String dedupKey = order.getEventId();
        if (seenStore.get(dedupKey) != null) {
            return null; // já visto — descarta
        }
        seenStore.put(dedupKey, System.currentTimeMillis());
        return order;
    }
}, "dedup-store");
```

```python
# Python / Redis com TTL: dedup barato para pipelines simples
def is_duplicate(redis_client, event_id: str, ttl_seconds: int = 3600) -> bool:
    # SETNX + TTL: atômico, retorna False na primeira vez, True em repetições
    was_set = redis_client.set(f"dedup:{event_id}", "1", nx=True, ex=ttl_seconds)
    return not was_set

for msg in consumer:
    event = msg.value
    if is_duplicate(redis, event["event_id"]):
        continue  # já processado, pula
    process(event)
    consumer.commit()
```

## Estratégia 3 — sink idempotente (upsert em vez de insert)

A forma mais robusta: desenhar o sink para que reprocessar o mesmo evento não mude o resultado
final — elimina a necessidade de rastrear "já vi essa chave".

```sql
-- Upsert por chave de negócio: reprocessar o mesmo evento não duplica nem corrompe
INSERT INTO orders_silver (order_id, customer_id, amount, updated_at)
VALUES (%(order_id)s, %(customer_id)s, %(amount)s, %(event_ts)s)
ON CONFLICT (order_id)
DO UPDATE SET
    amount = EXCLUDED.amount,
    updated_at = EXCLUDED.updated_at
WHERE EXCLUDED.updated_at > orders_silver.updated_at;  -- evita out-of-order overwrite
```

```python
# Delta Lake MERGE: mesma ideia, idempotente + tolerante a out-of-order
(
    DeltaTable.forName(spark, "silver.orders")
    .alias("t")
    .merge(new_events_df.alias("s"), "t.order_id = s.order_id")
    .whenMatchedUpdateAll(condition="s.event_ts > t.updated_at")
    .whenNotMatchedInsertAll()
    .execute()
)
```

## Comparando as 3 estratégias

| Estratégia | Custo | Robustez |
|---|---|---|
| Chave natural + dedup lógico | Baixo | Depende do evento ter identificador estável |
| State store com TTL | Médio (estado extra) | Boa para dedup dentro de janela curta |
| Sink idempotente (upsert) | Baixo a médio | **Mais robusta** — elimina a classe de problema |

Prefira sink idempotente sempre que possível — é a solução que não depende de "lembrar" nada.
Combine com dedup de state store quando o sink não suporta upsert nativamente (ex.: chamada de
API externa não-idempotente).

## Gotchas

- **`event_id` gerado no consumidor (não na origem) não deduplica nada** — precisa vir do
  produtor ou ser derivado de campos estáveis do evento (não de `uuid4()` a cada leitura).
- **Dedup por conteúdo do payload (hash) quebra se o mesmo evento de negócio tiver campos
  não-determinísticos** (timestamp de processamento embutido no payload, por exemplo).
- **State store sem TTL cresce sem limite** — sempre configure retenção; duplicatas legítimas
  raramente aparecem depois de horas/dias.
- **CDC (Debezium) reenvia o snapshot inicial inteiro se o connector for recriado do zero** —
  isso não é "bug", é `op: "r"` de um novo snapshot; trate como at-least-once normal.

## Referências
- `../concepts/delivery-semantics.md` — por que at-least-once é o padrão prático
- `cdc-debezium.md` — fonte comum de eventos duplicados em restart de connector
- `windowing.md` — state store com TTL usa a mesma mecânica de retenção
