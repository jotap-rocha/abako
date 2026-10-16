# Watermarking — Dados Atrasados em Streaming

## O problema

Em streaming, eventos chegam fora de ordem: rede lenta, retry, partição com lag, produtor
offline. Um evento com `event_time=10:00:00` pode chegar no processador às `10:00:45`.
Sem uma estratégia explícita, o job nunca sabe quando "fechar" uma janela de agregação —
pode sempre chegar mais um evento atrasado.

## Event time vs processing time vs ingestion time

| Tipo | O que é | Quando usar |
|---|---|---|
| **Event time** | Timestamp de quando o evento *aconteceu* na origem | Padrão para lógica de negócio (agregações corretas) |
| **Processing time** | Timestamp de quando o processador *viu* o evento | Simples, mas incorreto se a ordem importa |
| **Ingestion time** | Timestamp de quando o evento *entrou* no Kafka | Meio-termo — não depende do relógio da origem |

Regra: se a lógica de negócio depende de "quando o evento aconteceu" (ex.: valor de uma
transação no momento em que foi feita), use **event time** sempre.

## O que é watermark

Watermark é uma marca d'água que declara: "não espero mais eventos com `event_time` anterior a
X". É uma heurística, não uma garantia — sempre existe risco de dado atrasado além do watermark.

```
watermark(t) = max(event_time visto até agora) - allowed_lateness
```

## Estratégias de watermark (Flink)

```java
// Bounded out-of-orderness: aceita atraso de até 5 minutos
WatermarkStrategy
    .<Order>forBoundedOutOfOrderness(Duration.ofMinutes(5))
    .withTimestampAssigner((order, ts) -> order.getEventTimeMillis());
```

```python
# PySpark Structured Streaming — watermark declarado no DataFrame
stream = (
    spark.readStream.format("kafka").option("subscribe", "orders").load()
    .withWatermark("event_time", "5 minutes")
    .groupBy(window("event_time", "10 minutes"), "customer_id")
    .agg(sum("amount"))
)
```

## O que fazer com dados que chegam depois do watermark

1. **Descartar** — mais simples, aceitável se o volume de atraso extremo é desprezível
2. **Side output / DLQ separado** — captura o evento atrasado para reprocessamento manual ou
   auditoria (ver `../patterns/dead-letter-queue.md`)
3. **Atualização retroativa** — reabre a janela já emitida e reemite resultado corrigido
   (Flink `allowedLateness` com late output; caro, use só quando correção é obrigatória)

```java
// Flink: capturar eventos além do allowed lateness em side output
SingleOutputStreamOperator<Order> result = stream
    .keyBy(Order::getCustomerId)
    .window(TumblingEventTimeWindows.of(Time.minutes(10)))
    .allowedLateness(Time.minutes(2))
    .sideOutputLateData(lateOrdersTag)
    .sum("amount");

DataStream<Order> lateOrders = result.getSideOutput(lateOrdersTag);
lateOrders.addSink(deadLetterSink); // audita, não descarta silenciosamente
```

## Trade-off: janela maior de watermark vs latência

Watermark maior = mais tolerante a atraso = resultado mais correto, mas emitido mais tarde.
Watermark menor = resultado mais rápido, mas mais eventos descartados como "atrasados demais".

| Cenário | Watermark recomendado |
|---|---|
| Dashboard operacional em tempo real | Curto (segundos a 1 min) — latência importa mais que 100% de completude |
| Agregação financeira/fraude | Longo (5-15 min) — correção importa mais que velocidade |
| IoT com dispositivos offline | Muito longo (horas) ou late-arrival handling separado |

## Gotchas

- **Nunca use processing time para lógica de negócio que depende de ordem** — resultado muda
  dependendo de quando o processador estava ocupado, não do que realmente aconteceu.
- **Watermark não é uma garantia** — é sempre possível que um evento chegue depois do watermark
  avançar. Trate isso explicitamente (não assuma "nunca vai acontecer").
- **Watermark parado (stalled)** quando uma partição fica sem tráfego — o watermark global fica
  preso no mínimo entre partições. Configure timeout de idle source (`withIdleness` no Flink).
- **Reprocessamento (replay) sem cuidado com watermark** pode descartar todos os dados como
  "atrasados" se o watermark inicial não for resetado corretamente.

## Referências
- `delivery-semantics.md` — garantias de entrega, ortogonal a watermarking
- `../patterns/windowing.md` — como watermark interage com tumbling/sliding/session windows
- `../patterns/dead-letter-queue.md` — destino para eventos descartados por atraso
