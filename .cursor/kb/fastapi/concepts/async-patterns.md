# Padrões Async no FastAPI

## Regra fundamental

```
I/O (DB, HTTP externo, arquivo) → async def + await
CPU puro (cálculo, transformação) → def síncrono (FastAPI roda em thread pool)
```

## Connection pool — criar no lifespan, nunca por request

```python
from contextlib import asynccontextmanager
import asyncpg
from fastapi import FastAPI

@asynccontextmanager
async def lifespan(app: FastAPI):
    # startup — cria uma vez
    app.state.db_pool = await asyncpg.create_pool(
        dsn=settings.database_url,
        min_size=2,
        max_size=10,
        command_timeout=30,
    )
    yield
    # shutdown — fecha ao encerrar
    await app.state.db_pool.close()

app = FastAPI(lifespan=lifespan)
```

## Async DB com asyncpg

```python
async def fetch_products(pool: asyncpg.Pool, category: str) -> list[dict]:
    async with pool.acquire() as conn:
        rows = await conn.fetch(
            "SELECT id, name, price FROM products WHERE category = $1 LIMIT 100",
            category,
        )
    return [dict(r) for r in rows]
```

## HTTP externo com httpx

```python
import httpx

# Client reutilizável no lifespan
@asynccontextmanager
async def lifespan(app: FastAPI):
    async with httpx.AsyncClient(timeout=10.0) as http:
        app.state.http = http
        yield

# Uso no service
async def call_external_api(url: str, app_state) -> dict:
    resp = await app_state.http.get(url)
    resp.raise_for_status()
    return resp.json()
```

## Streaming response (SSE)

```python
from fastapi.responses import StreamingResponse
import asyncio

@router.post("/chat/stream")
async def chat_stream(
    body: ChatRequest,
    service: ChatService = Depends(get_chat_service),
):
    async def generate():
        async for chunk in service.stream(body.query, body.session_id):
            yield f"data: {chunk}\n\n"
        yield "data: [DONE]\n\n"

    return StreamingResponse(
        generate(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )
```

## Background tasks — fire and forget

```python
from fastapi import BackgroundTasks

async def log_interaction(query: str, answer: str, session_id: str):
    """Grava no harness — não bloqueia a resposta."""
    await harness.record(query=query, answer=answer, session_id=session_id)

@router.post("/chat", response_model=ChatResponse)
async def chat(
    body: ChatRequest,
    background_tasks: BackgroundTasks,
    service: ChatService = Depends(get_chat_service),
):
    result = await service.process(body.query, body.session_id)
    # Registrar em background — não atrasa a resposta
    background_tasks.add_task(log_interaction, body.query, result.answer, body.session_id)
    return ChatResponse(answer=result.answer, sources=result.sources)
```

## Timeout em operações async

```python
import asyncio

async def with_timeout(coro, timeout: float, fallback=None):
    try:
        return await asyncio.wait_for(coro, timeout=timeout)
    except asyncio.TimeoutError:
        return fallback

# Uso:
result = await with_timeout(
    service.process(body.query, body.session_id),
    timeout=30.0,
    fallback=ServiceResult(error="Timeout — tente novamente"),
)
```

## Anti-padrões

```python
# ERRADO: bloqueante em rota async
@router.post("/chat")
async def chat(body: ChatRequest):
    import time
    time.sleep(1)                          # bloqueia o event loop inteiro
    result = requests.get("http://...")    # bloqueante — usar httpx.AsyncClient

# ERRADO: criar conexão por request
@router.post("/chat")
async def chat(body: ChatRequest):
    pool = await asyncpg.create_pool(dsn=...)  # caro demais por request
    ...
    await pool.close()

# CERTO: pool do lifespan via Depends
@router.post("/chat")
async def chat(body: ChatRequest, db=Depends(get_db)):
    ...
```
