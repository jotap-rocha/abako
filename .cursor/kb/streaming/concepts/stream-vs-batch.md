# Stream vs Batch — Modelo de Processamento

## O que muda

| Dimensão | Batch | Streaming |
|---|---|---|
| Dataset | Limitado (bounded), conhecido no início | Ilimitado (unbounded), infinito por definição |
| Latência | Minutos a horas (janela de execução) | Milissegundos a segundos (contínuo) |
| Execução | Job roda, processa tudo, termina | Job roda continuamente, nunca "termina" |
| Reprocessamento | Reroda o job inteiro | Replay de offsets específicos (Kafka) |
| Estado | Recalculado do zero a cada run | Mantido incrementalmente (state store) |
| Falha | Reroda o batch | Checkpoint + resume do último ponto consistente |

## Streaming não é "batch com intervalo menor"

Reduzir o intervalo de um batch job de 1h para 1min não vira streaming — ainda processa
snapshots discretos e recalcula do zero. Streaming real processa **evento a evento** (ou
micro-batch com estado incremental), mantém estado entre execuções e lida com dados que chegam
fora de ordem (ver `watermarking.md`).

## Two lados do mesmo pipeline

Não é uma escolha binária por projeto — é comum coexistirem na arquitetura Medallion
(`.claude/kb/pipeline/concepts/medallion.md`):

```
Kafka (streaming) → Bronze (streaming, near-real-time)
                        ↓
                   Silver (streaming ou batch — depende do SLA)
                        ↓
                   Gold (batch — agregações pesadas, BI)
```

Regra prática: streaming onde a latência importa (fraude, alertas, dashboards operacionais);
batch onde throughput/custo importa mais que latência (relatórios diários, treino de ML).

## Quando usar streaming

- SLA de latência < 1 minuto (detecção de fraude, alertas operacionais)
- Fonte é naturalmente um stream de eventos (cliques, transações, IoT, CDC de banco)
- Necessidade de reagir a cada evento individualmente (não só agregados)

## Quando usar batch

- Volume grande, latência não é crítica (relatórios, treino de modelo)
- Transformações complexas que precisam do dataset completo (joins pesados, window functions
  sobre histórico inteiro)
- Custo de infraestrutura de streaming (cluster sempre ligado) não se justifica

## Exemplo conceitual — mesma lógica, dois modelos

```python
# Batch: processa tudo de uma vez, job termina
def batch_job():
    df = spark.read.parquet("bronze/orders")
    result = df.groupBy("customer_id").agg(sum("amount"))
    result.write.mode("overwrite").saveAsTable("gold.customer_totals")
    # job termina aqui — próxima execução recalcula tudo (ou incremental via merge)

# Streaming: processa evento a evento, nunca termina
def streaming_job():
    stream = spark.readStream.format("kafka").option("subscribe", "orders").load()
    result = stream.groupBy("customer_id").agg(sum("amount"))
    query = result.writeStream.outputMode("update").start()
    query.awaitTermination()  # roda indefinidamente
```

## Gotchas

- **Estado não-bounded cresce sem limite** se a chave de agregação não tiver TTL — sempre defina
  retenção de estado (ver `windowing.md`) ou o job explode em memória/disco.
- **"Streaming" com Spark Structured Streaming em modo `Trigger.Once` é batch disfarçado** —
  útil para simular streaming barato, mas não tem os mesmos SLAs de latência.
- Fonte "quase streaming" (arquivo caindo em bucket a cada 5 min) não é evento a evento — é
  micro-batch. Trate como batch se a fonte não é nativamente um stream de eventos.

## Referências
- `watermarking.md` — como lidar com dados fora de ordem em streaming
- `../patterns/windowing.md` — agregação em streaming sem estado ilimitado
- `.claude/kb/pipeline/concepts/medallion.md` — onde streaming se encaixa no Medallion
