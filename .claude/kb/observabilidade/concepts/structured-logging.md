# Structured Logging com structlog

## Por que logging estruturado

Log de string livre (`print("erro ao processar query")`) é infiltrável.
Log estruturado (`log.error("query.error", session_id=..., error=...)`) é consultável, alertável e correlacionável.

## Setup com structlog

```python
# backend/app/logging.py
import structlog
import logging

def configure_logging(debug: bool = False):
    logging.basicConfig(
        format="%(message)s",
        level=logging.DEBUG if debug else logging.INFO,
    )

    structlog.configure(
        processors=[
            structlog.contextvars.merge_contextvars,
            structlog.processors.add_log_level,
            structlog.processors.TimeStamper(fmt="iso"),
            structlog.processors.StackInfoRenderer(),
            structlog.dev.ConsoleRenderer() if debug else structlog.processors.JSONRenderer(),
        ],
        wrapper_class=structlog.make_filtering_bound_logger(
            logging.DEBUG if debug else logging.INFO
        ),
        context_class=dict,
        logger_factory=structlog.PrintLoggerFactory(),
    )

# Chamar no lifespan do FastAPI
configure_logging(debug=settings.debug)
```

## Uso básico

```python
import structlog
log = structlog.get_logger(__name__)

# Campos base por módulo
log = log.bind(component="chat_service")

# Log de request
log.info("request.start", session_id=session_id, query_len=len(query))

# Log de resultado
log.info("request.done", session_id=session_id, latency_ms=elapsed, intent=intent)

# Log de warning (resultado inesperado mas tratado)
log.warning("search.empty", session_id=session_id, collection="docs_privados")

# Log de erro
log.error("llm.timeout", session_id=session_id, timeout_secs=30, exc_info=True)
```

## Campos obrigatórios por camada

| Camada | Campos obrigatórios |
|---|---|
| **Router (request)** | `session_id`, `method`, `path` |
| **Service** | `session_id`, `component`, `latency_ms` |
| **Agente / nó** | `session_id`, `node`, `intent` |
| **Tool SQL** | `session_id`, `table`, `rows_returned`, `latency_ms` |
| **Tool Search** | `session_id`, `collection`, `hits`, `latency_ms` |
| **LLM call** | `session_id`, `model`, `input_tokens`, `output_tokens`, `latency_ms` |
| **Erro** | `session_id`, `component`, `error_code`, `exc_info=True` |

## Context vars — propagar session_id automaticamente

```python
import structlog

# No início de cada request (middleware ou Depends)
async def logging_middleware(request: Request, call_next):
    session_id = request.headers.get("X-Session-ID", str(uuid4()))
    structlog.contextvars.clear_contextvars()
    structlog.contextvars.bind_contextvars(
        session_id=session_id,
        request_id=str(uuid4()),
    )
    response = await call_next(request)
    return response

# A partir daí, todo log no request já tem session_id automaticamente
log.info("service.start")  # → {"session_id": "...", "request_id": "...", "event": "service.start"}
```

## O que NÃO logar

```python
# NUNCA: PII em logs
log.info("user.login", email=user.email)        # ❌ PII
log.info("payment", cpf=customer.cpf)           # ❌ PII
log.info("query", content=user_query)           # ❌ pode conter PII

# CERTO: mascarar ou omitir
log.info("user.login", user_id=user.id)         # ✅ ID anônimo
log.info("payment", payment_id=payment.id)      # ✅ ID sem PII
log.info("query", query_len=len(user_query))    # ✅ só metadado
```

## Formato JSON em produção

```json
{
  "timestamp": "2026-06-27T10:23:45.123Z",
  "level": "info",
  "event": "chat.done",
  "component": "chat_service",
  "session_id": "sess-abc123",
  "intent": "sql_aggregate",
  "latency_ms": 1243,
  "sources_count": 3
}
```
