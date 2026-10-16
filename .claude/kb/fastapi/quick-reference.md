---
domain: fastapi
topic: quick-reference
---

# FastAPI — Quick Reference

### Layout canônico

```
backend/
├── app/
│   ├── main.py              ← FastAPI() + include_router + lifespan
│   ├── routers/
│   │   ├── chat.py          ← router.post("/chat") → service.chat()
│   │   ├── health.py        ← router.get("/health")
│   │   └── __init__.py
│   ├── services/
│   │   ├── chat_service.py  ← lógica de negócio, sem HTTP
│   │   └── __init__.py
│   ├── schemas/
│   │   ├── chat.py          ← ChatRequest, ChatResponse (Pydantic)
│   │   └── error.py         ← ErrorResponse
│   └── deps.py              ← get_db(), get_current_user(), get_config()
```

### Invariantes

| # | Invariante |
|---|---|
| FA-01 | Router não contém lógica de negócio — apenas valida input, chama service, retorna output |
| FA-02 | Toda dependência (DB, auth, config) via `Depends()` — sem import global mutável |
| FA-03 | Sem PII em URL ou query params — usar body (POST) ou headers |
| FA-04 | Toda rota tem `response_model` declarado — sem `dict` como retorno |
| FA-05 | Error responses usam `ErrorResponse` schema padronizado — sem strings brutas |
| FA-06 | Connection pool criado no lifespan — nunca a cada request |

### Decision tree: quando async vs sync

```
A operação faz I/O? (DB, HTTP externo, arquivo)
    ├── SIM → async def + await
    │         ├── DB: asyncpg ou SQLAlchemy async
    │         └── HTTP: httpx.AsyncClient
    └── NÃO (só CPU) → def síncrono
                       (FastAPI roda em thread pool automaticamente)
```
