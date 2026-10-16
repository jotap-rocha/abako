# Windowing — Tumbling, Sliding, Session

## Por que janelas

Streams são infinitos — agregação (`sum`, `count`, `avg`) precisa de um limite finito para
"fechar" e emitir resultado. Janela é esse limite, definido por tempo (event time, ver
`../concepts/watermarking.md`) ou por contagem de eventos.

## Tumbling window (janela fixa, sem sobreposição)

Divide o tempo em blocos fixos e não sobrepostos. Cada evento pertence a exatamente uma janela.

```
[0-10min) [10-20min) [20-30min) ...
   ↑ evento às 10:03 cai aqui
```

```java
// Flink
stream
    .keyBy(Order::getCustomerId)
    .window(TumblingEventTimeWindows.of(Time.minutes(10)))
    .sum("amount");
```

```java
// Kafka Streams
KGroupedStream<String, Order> grouped = stream.groupByKey();
grouped
    .windowedBy(TimeWindows.ofSizeWithNoGrace(Duration.ofMinutes(10)))
    .aggregate(() -> 0.0, (key, order, total) -> total + order.getAmount());
```

**Uso típico**: métricas periódicas ("total de pedidos a cada 10 minutos"), dashboards com
granularidade fixa.

## Sliding window (janela deslizante, com sobreposição)

Janela de tamanho fixo que avança em incrementos menores que o próprio tamanho — um evento pode
pertencer a múltiplas janelas simultaneamente.

```
Janela de 10min, deslizando a cada 5min:
[0-10min) [5-15min) [10-20min) ...
   ↑ evento às 10:03 cai em [5-15min) E [10-20min)
```

```java
// Flink
stream
    .keyBy(Order::getCustomerId)
    .window(SlidingEventTimeWindows.of(Time.minutes(10), Time.minutes(5)))
    .sum("amount");
```

**Uso típico**: médias móveis, detecção de anomalia ("volume nos últimos 10min, atualizado a
cada 5min") — mais caro computacionalmente que tumbling (mais janelas ativas por evento).

## Session window (janela por inatividade)

Agrupa eventos próximos no tempo; a janela fecha após um período de inatividade (gap). Sem
tamanho fixo — depende do padrão de chegada dos eventos.

```
Eventos: 10:00, 10:02, 10:03, [gap de 15min], 10:20, 10:21
Gap de 5min → Session 1: [10:00-10:03], Session 2: [10:20-10:21]
```

```java
// Flink
stream
    .keyBy(Order::getCustomerId)
    .window(EventTimeSessionWindows.withGap(Time.minutes(5)))
    .sum("amount");
```

**Uso típico**: sessão de usuário (cliques em uma visita ao site), sequência de transações
relacionadas ("todas as tentativas de compra do mesmo cartão em uma janela de atividade").

## Escolhendo o tipo de janela

| Caso de uso | Tipo de janela |
|---|---|
| Métrica agregada por intervalo fixo (dashboards) | Tumbling |
| Média móvel / detecção de tendência | Sliding |
| Comportamento de sessão do usuário | Session |
| Detecção de fraude por rajada de eventos | Session (gap curto, ex: 2-5 min) |
| Reconciliação financeira por hora/dia | Tumbling |

## Watermark + allowed lateness + trigger

Janela sozinha não resolve dados atrasados — combine com watermark
(`../concepts/watermarking.md`):

```java
stream
    .keyBy(Order::getCustomerId)
    .window(TumblingEventTimeWindows.of(Time.minutes(10)))
    .allowedLateness(Time.minutes(2))       // aceita atraso extra depois do watermark
    .sideOutputLateData(lateDataTag)        // captura o que passou do allowed lateness
    .sum("amount");
```

Sem `allowedLateness`, a janela fecha estritamente no watermark e qualquer evento posterior é
descartado silenciosamente — sempre decida explicitamente o que fazer com dado atrasado.

## Retenção de estado — janela não é grátis

Cada janela ativa mantém estado (RocksDB no Flink, state store no Kafka Streams) até fechar.
Muitas keys × muitas janelas simultâneas = estado grande.

```java
// Kafka Streams: TTL explícito de retenção do state store da janela
TimeWindows.ofSizeAndGrace(Duration.ofMinutes(10), Duration.ofMinutes(2))
```

## Gotchas

- **Tumbling window "parece" simples mas emite resultado só no fechamento** — se precisar de
  resultado incremental (early firing), use trigger customizado (`.trigger()` no Flink).
- **Sliding window com incremento pequeno explode o número de janelas ativas** — cada evento
  entra em `tamanho/incremento` janelas simultâneas. Dimensione o state store de acordo.
- **Session window sem limite máximo de duração** pode nunca fechar se o padrão de chegada for
  contínuo com gaps sempre menores que o threshold — considere `withDynamicGap` ou timeout
  absoluto adicional.
- **Chave errada no `keyBy`** (ex.: agregando globalmente sem particionar por customer/tenant)
  concentra todo o estado em uma única task — gargalo de paralelismo.

## Referências
- `../concepts/watermarking.md` — event time e tratamento de atraso, pré-requisito de windowing
- `deduplication.md` — deduplicação frequentemente usa state store com TTL, mesma mecânica
