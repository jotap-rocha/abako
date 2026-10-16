---
domain: observabilidade
topic: quick-reference
---

# Observabilidade — Quick Reference

### Stack de observabilidade

```
Agente LLM  →  Langfuse (traces + scores + datasets)
Pipeline    →  structured logging (structlog) + métricas customizadas
Infra       →  docker stats, healthcheck endpoints
```

### Campos obrigatórios em todo log

```python
log.info("evento", **{
    "session_id": session_id,
    "user_id":    user_id,
    "latency_ms": elapsed_ms,
    "component":  "chat_service",
})
```

### Níveis de log por situação

| Situação | Nível |
|---|---|
| Request recebido / processado | `info` |
| Resultado inesperado (mas não erro) | `warning` |
| Exceção capturada e tratada | `error` |
| Erro não recuperável / bug | `critical` |
| Debug de desenvolvimento | `debug` (desativar em produção) |

### Invariantes

| # | Invariante |
|---|---|
| OBS-01 | Toda chamada LLM tem trace no Langfuse (session_id, input, output, latência, custo) |
| OBS-02 | Nunca logar PII (CPF, email, dados financeiros) — mascarar antes do log |
| OBS-03 | `session_id` presente em todo log e trace — peça de rastreamento |
| OBS-04 | Scores de qualidade (grounding, relevância) gravados após avaliação humana ou automática |
| OBS-05 | Alertas configurados para: latência p95 > 10s, custo/dia > threshold, error_rate > 5% |
