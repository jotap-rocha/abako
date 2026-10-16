# CDC (Change Data Capture) com Debezium

## O que é

CDC captura mudanças (`INSERT`/`UPDATE`/`DELETE`) de um banco de dados em tempo real e as
publica como eventos em um stream — sem polling, sem dual-write manual. Debezium faz isso
lendo o **log de transações** do banco (WAL no Postgres, binlog no MySQL), não a tabela em si.

```
Banco (Postgres/MySQL) → transaction log → Debezium connector → Kafka Connect → tópico Kafka
```

Log-based CDC (Debezium) é preferível a polling (`SELECT * WHERE updated_at > last_run`) porque:
captura `DELETE` (polling não vê linhas apagadas), não perde updates entre polls, e não
sobrecarrega o banco com queries repetidas.

## Arquitetura

```
┌──────────┐     WAL/binlog      ┌───────────┐   Kafka Connect  ┌──────────────┐
│ Postgres │ ───────────────────▶│ Debezium  │ ────────────────▶│ Kafka topics │
│ (source) │                     │ connector │                  │ orders.public.*│
└──────────┘                     └───────────┘                  └──────────────┘
```

Cada tabela vira um tópico (`{server}.{schema}.{table}`, ex.: `orders_db.public.orders`).
Cada evento tem `before` (estado antes) e `after` (estado depois) — permite reconstruir o
delta exato de qualquer mudança.

## Configuração do connector (Postgres)

```json
{
  "name": "orders-connector",
  "config": {
    "connector.class": "io.debezium.connector.postgresql.PostgresConnector",
    "database.hostname": "postgres",
    "database.port": "5432",
    "database.user": "${env:DEBEZIUM_DB_USER}",
    "database.password": "${env:DEBEZIUM_DB_PASSWORD}",
    "database.dbname": "orders_db",
    "topic.prefix": "orders_db",
    "table.include.list": "public.orders,public.order_items",
    "plugin.name": "pgoutput",
    "publication.autocreate.mode": "filtered",
    "key.converter": "org.apache.kafka.connect.json.JsonConverter",
    "value.converter": "org.apache.kafka.connect.json.JsonConverter",
    "tombstones.on.delete": "true"
  }
}
```

Credenciais **sempre via variável de ambiente/secret manager** — nunca hardcoded no config
(ver `.claude/rules/seguranca.md`).

## Formato do evento

```json
{
  "before": null,
  "after": {"id": 501, "customer_id": 42, "amount": 199.90, "status": "pending"},
  "source": {"table": "orders", "ts_ms": 1721990400000, "lsn": 123456789},
  "op": "c",
  "ts_ms": 1721990400123
}
```

`op`: `c` (create), `u` (update), `d` (delete), `r` (read — snapshot inicial).

## Snapshot inicial vs streaming contínuo

- **Snapshot**: na primeira execução, Debezium lê o estado atual completo da tabela (`op: "r"`)
  antes de começar a seguir o log — necessário para capturar dados já existentes.
- **Streaming**: depois do snapshot, segue o log continuamente, evento a evento.

```json
"snapshot.mode": "initial"   // snapshot completo + depois streaming (padrão)
"snapshot.mode": "no_data"   // pula snapshot, só streaming a partir de agora
```

## Outbox pattern — CDC para eventos de domínio (não CRUD cru)

Publicar direto a tabela transacional via CDC vazou detalhes de implementação do schema para
consumidores. O padrão outbox desacopla:

```sql
-- Tabela outbox: escrita na MESMA transação que a mudança de negócio
CREATE TABLE outbox_events (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    aggregate_type TEXT NOT NULL,   -- "order"
    aggregate_id TEXT NOT NULL,     -- order_id
    event_type TEXT NOT NULL,       -- "OrderCreated"
    payload JSONB NOT NULL,
    created_at TIMESTAMPTZ DEFAULT now()
);
```

```python
# Escrita atômica: mudança de negócio + evento outbox na mesma transação
with db.transaction():
    db.execute("INSERT INTO orders (...) VALUES (...)")
    db.execute(
        "INSERT INTO outbox_events (aggregate_type, aggregate_id, event_type, payload) "
        "VALUES (%s, %s, %s, %s)",
        ["order", order_id, "OrderCreated", json.dumps(event_payload)],
    )
# Debezium captura só a tabela outbox_events, não as tabelas de domínio internas
```

Debezium tem um **Outbox Event Router** SMT (Single Message Transform) nativo para isso.

## Gotchas

- **CDC gera duplicatas em restart do connector** — sempre desenhe o consumidor para ser
  idempotente (ver `deduplication.md`), nunca assuma exactly-once do connector.
- **Mudança de schema na tabela fonte quebra o connector** se não houver schema registry —
  use Avro/Protobuf + Schema Registry (compatibilidade `BACKWARD`) para evoluir sem quebrar.
- **Tombstone events (`op: null`, value `null`) representam delete lógico no compacted topic** —
  não descarte silenciosamente; são o sinal de que a linha foi apagada.
- **CDC não é backup nem substitui auditoria transacional** — é um stream de mudanças, não um
  histórico garantido (retenção do tópico Kafka é finita).
- **Nunca fazer CDC direto de tabela com PII sem mascaramento** — o evento propaga o dado cru
  para todos os consumidores do tópico. Aplique masking SMT ou publique só campos necessários.
- **`table.include.list` explícito é obrigatório** — sem allowlist, qualquer tabela nova no
  schema vira tópico automaticamente, vazando dados não previstos.

## Referências
- `../concepts/delivery-semantics.md` — por que CDC exige consumidor idempotente
- `deduplication.md` — implementação de idempotência para eventos duplicados de CDC
- `.claude/rules/seguranca.md` — regras de PII aplicáveis a payloads de CDC
