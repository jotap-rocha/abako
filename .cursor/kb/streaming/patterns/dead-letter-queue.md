# Dead-Letter Queue (DLQ) — Eventos com Erro

## O problema

Um evento malformado, com schema incompatível, ou que causa exceção no processamento não pode
travar o pipeline inteiro (poison message). Sem DLQ, o consumidor trava em loop de retry no
mesmo offset (crash → restart → mesmo evento → crash) ou, pior, o offset é commitado e o evento
é perdido silenciosamente.

## Padrão básico — captura + roteamento

```python
from kafka import KafkaProducer, KafkaConsumer
import json, traceback

dlq_producer = KafkaProducer(bootstrap_servers="kafka:9092")

def process_with_dlq(consumer: KafkaConsumer, main_topic: str, dlq_topic: str):
    for msg in consumer:
        try:
            event = json.loads(msg.value)
            process(event)
            consumer.commit()
        except Exception as e:
            dlq_payload = {
                "original_topic": msg.topic,
                "original_partition": msg.partition,
                "original_offset": msg.offset,
                "original_value": msg.value.decode("utf-8", errors="replace"),
                "error": str(e),
                "error_type": type(e).__name__,
                "traceback": traceback.format_exc(),
                "failed_at": datetime.utcnow().isoformat(),
            }
            dlq_producer.send(dlq_topic, value=json.dumps(dlq_payload).encode())
            dlq_producer.flush()
            consumer.commit()  # commita o original mesmo em erro — não trava o pipeline
```

**Nunca** deixar de commitar o offset original após enviar para a DLQ — senão o consumidor
reprocessa o mesmo evento com erro para sempre (loop infinito de poison message).

## Retry topic com backoff antes da DLQ final

Nem todo erro é permanente — timeout de rede, serviço externo temporariamente fora, throttling.
Padrão de retry topics com backoff crescente evita jogar na DLQ um erro transitório:

```
orders (principal)
   │ erro
   ▼
orders-retry-1min  (delay de 1min antes de reprocessar)
   │ erro de novo
   ▼
orders-retry-5min  (delay de 5min)
   │ erro de novo
   ▼
orders-dlq  (definitivo — precisa de intervenção humana)
```

```python
RETRY_TOPICS = [("orders-retry-1min", 60), ("orders-retry-5min", 300)]

def route_on_failure(event: dict, attempt: int, dlq_producer):
    if attempt < len(RETRY_TOPICS):
        topic, delay_seconds = RETRY_TOPICS[attempt]
        event["_retry_attempt"] = attempt + 1
        event["_retry_after"] = (datetime.utcnow() + timedelta(seconds=delay_seconds)).isoformat()
        dlq_producer.send(topic, value=json.dumps(event).encode())
    else:
        dlq_producer.send("orders-dlq", value=json.dumps(event).encode())
```

Kafka Connect tem suporte nativo a DLQ via config (sem código customizado):

```json
{
  "errors.tolerance": "all",
  "errors.deadletterqueue.topic.name": "orders-connect-dlq",
  "errors.deadletterqueue.context.headers.enable": "true",
  "errors.log.enable": "true"
}
```

## Classificando o tipo de erro antes de rotear

Nem todo erro deve ir para retry — erros permanentes (schema inválido, dado corrompido) só
desperdiçam ciclos de retry. Roteie por classe de erro:

```python
def classify_error(e: Exception) -> str:
    if isinstance(e, (TimeoutError, ConnectionError)):
        return "transient"   # vai para retry topic
    if isinstance(e, (ValueError, SchemaValidationError)):
        return "permanent"   # vai direto para DLQ, sem retry
    return "unknown"          # tratar como transient com limite de tentativas
```

## Alertas e reprocessamento

DLQ sem monitoramento é um buraco negro. Sempre acoplar:

- **Alerta** quando volume na DLQ cresce acima de um threshold (ver
  `.claude/kb/observabilidade/patterns/alert-thresholds.md`)
- **Dashboard** com contagem de mensagens na DLQ por tipo de erro
- **Processo de reprocessamento manual** — depois do fix, reenviar da DLQ para o tópico
  principal (nunca "apagar e esquecer")

```python
def reprocess_from_dlq(dlq_consumer, main_producer, main_topic):
    for msg in dlq_consumer:
        dlq_event = json.loads(msg.value)
        main_producer.send(main_topic, value=dlq_event["original_value"].encode())
        dlq_consumer.commit()
```

## Gotchas

- **Commitar o offset original SEM enviar para a DLQ é perda de dado silenciosa** — sempre
  garanta que o envio à DLQ teve sucesso (flush síncrono ou callback) antes de commitar.
- **DLQ sem contexto suficiente** (só o payload cru, sem erro/timestamp/offset original) torna o
  reprocessamento manual quase impossível — sempre inclua metadata de diagnóstico.
- **Retry infinito sem backoff crescente** satura o pipeline com o mesmo erro repetidamente —
  sempre usar backoff exponencial ou tópicos de retry escalonados.
- **PII em payload de DLQ** — a DLQ costuma ter retenção mais longa (para debug) e é acessada
  por mais gente (SRE, dev) — aplique as mesmas regras de mascaramento de PII
  (`.claude/rules/seguranca.md`) no payload armazenado.

## Referências
- `deduplication.md` — reprocessamento da DLQ pode reintroduzir duplicatas, combine com dedup
- `.claude/kb/observabilidade/patterns/alert-thresholds.md` — alertas de volume na DLQ
- `.claude/rules/seguranca.md` — PII em payloads de erro
