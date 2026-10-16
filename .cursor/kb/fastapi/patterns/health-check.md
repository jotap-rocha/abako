# Padrão Health Check

## Health check com verificação real das dependências

```python
# backend/app/routers/health.py
from fastapi import APIRouter, Request, status
from fastapi.responses import JSONResponse
from pydantic import BaseModel
import asyncio

router = APIRouter(tags=["Health"])

class DependencyStatus(BaseModel):
    name: str
    ok: bool
    latency_ms: float | None = None
    error: str | None = None

class HealthResponse(BaseModel):
    status: str           # "healthy" | "degraded" | "unhealthy"
    version: str
    dependencies: list[DependencyStatus]

async def check_postgres(pool) -> DependencyStatus:
    import time
    t0 = time.monotonic()
    try:
        async with pool.acquire() as conn:
            await asyncio.wait_for(conn.fetchval("SELECT 1"), timeout=2.0)
        return DependencyStatus(name="postgres", ok=True,
                                latency_ms=(time.monotonic() - t0) * 1000)
    except Exception as e:
        return DependencyStatus(name="postgres", ok=False, error=str(e))

async def check_qdrant(client) -> DependencyStatus:
    import time
    t0 = time.monotonic()
    try:
        client.get_collections()  # chamada leve
        return DependencyStatus(name="qdrant", ok=True,
                                latency_ms=(time.monotonic() - t0) * 1000)
    except Exception as e:
        return DependencyStatus(name="qdrant", ok=False, error=str(e))

@router.get("/health", response_model=HealthResponse)
async def health(request: Request):
    checks = await asyncio.gather(
        check_postgres(request.app.state.db_pool),
        check_qdrant(request.app.state.qdrant),
        return_exceptions=True,
    )

    deps: list[DependencyStatus] = []
    for c in checks:
        if isinstance(c, Exception):
            deps.append(DependencyStatus(name="unknown", ok=False, error=str(c)))
        else:
            deps.append(c)

    all_ok = all(d.ok for d in deps)
    http_status = status.HTTP_200_OK if all_ok else status.HTTP_503_SERVICE_UNAVAILABLE

    return JSONResponse(
        status_code=http_status,
        content=HealthResponse(
            status="healthy" if all_ok else "unhealthy",
            version=request.app.version,
            dependencies=deps,
        ).model_dump(),
    )

# Liveness simples (sem verificar dependências — para k8s)
@router.get("/health/live")
async def liveness():
    return {"status": "alive"}

# Readiness (com dependências — para k8s)
@router.get("/health/ready")
async def readiness(request: Request):
    pg = await check_postgres(request.app.state.db_pool)
    if not pg.ok:
        return JSONResponse(status_code=503, content={"status": "not ready", "reason": pg.error})
    return {"status": "ready"}
```

## nginx upstream check

```nginx
# infra/nginx/nginx.conf
upstream backend {
    server backend:8000;
}

location /health {
    proxy_pass http://backend/v1/health/live;
    access_log off;
}
```

## Uso no docker-compose

```yaml
services:
  backend:
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:8000/v1/health/live"]
      interval: 30s
      timeout: 5s
      retries: 3
      start_period: 10s
```

## O que verificar por tipo de dependência

| Dependência | Verificação | Timeout |
|---|---|---|
| Postgres | `SELECT 1` | 2s |
| Qdrant | `get_collections()` | 2s |
| Redis | `ping()` | 1s |
| LLM externo | pequena chamada de embedding | 5s |
| MinIO/S3 | `list_buckets()` | 3s |

## Regras

- `/health` verifica dependências reais — retorna 503 se qualquer crítica falhar
- `/health/live` retorna sempre 200 (app está de pé) — sem verificar deps
- Timeout em cada check — nunca pendurar na resposta por indefinido
- Latência medida e retornada — facilita diagnóstico de degradação lenta
