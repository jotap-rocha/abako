---
domain: streaming
topic: quick-reference
---

# Streaming — Quick Reference

### Semânticas de entrega

| Semântica | Garantia | Como obter |
|---|---|---|
| At-most-once | 0 ou 1 entrega | Auto-commit de offset (padrão, arriscado) |
| At-least-once | 1+ entregas | Commit manual após efeito colateral (padrão de fato) |
| Exactly-once | Exatamente 1 efeito líquido | Transações (Kafka Streams EOS, Flink 2PC) ou at-least-once + dedup |

### Tipos de janela

| Janela | Sobreposição | Uso típico |
|---|---|---|
| Tumbling | Não | Métrica fixa por intervalo (dashboard) |
| Sliding | Sim | Média móvel, detecção de tendência |
| Session | Dinâmica (gap-based) | Sessão de usuário, rajada de eventos |

### Estratégias de deduplicação (da mais simples à mais robusta)

1. Chave de idempotência natural (order_id, `(table, pk, lsn)` em CDC)
2. State store com TTL (dedup dentro de janela curta)
3. **Sink idempotente (upsert/MERGE)** — mais robusta, elimina a classe de problema

### Decision tree: erro no processamento de um evento

```
Evento falhou ao processar?
    ├── Erro é TRANSIENTE (timeout, conexão)?
    │   └── Retry topic com backoff (1min → 5min → ...)
    ├── Erro é PERMANENTE (schema inválido, dado corrompido)?
    │   └── DLQ direto (sem retry) + alerta
    └── Excedeu limite de retries?
        └── DLQ final + alerta + commit do offset original
              (nunca deixar de commitar — trava o pipeline)
```

### Decision tree: streaming ou batch?

```
SLA de latência < 1 minuto?
    ├── SIM → streaming
    └── NÃO
        └── Fonte é naturalmente um stream de eventos (CDC, cliques, IoT)?
            ├── SIM → streaming (Bronze) + batch (Silver/Gold) é comum
            └── NÃO → batch
```

### Kafka partitioning — regras rápidas

- Ordem garantida **só dentro da partição** — mesma key sempre na mesma partição
- Nº de partições ≥ nº máximo de consumidores paralelos
- Aumentar partições depois quebra ordenação por key existente (novo hash space)

### CDC (Debezium) — checklist mínimo

- [ ] `table.include.list` explícito (nunca capturar schema inteiro por padrão)
- [ ] Credenciais via env var/secret manager, nunca hardcoded no connector config
- [ ] Consumidor idempotente (CDC é sempre at-least-once na prática)
- [ ] Masking de PII antes de publicar, se a tabela fonte tiver dados pessoais
- [ ] Outbox pattern se o consumidor não deve depender do schema interno da tabela
