# Dependency Injection com Depends()

## Por que usar

- Sem global state mutável — cada request recebe sua própria instância
- Testável — substituir por mock em testes sem monkey-patching
- Lifecycle gerenciado — conexões abertas e fechadas no momento certo

## Padrão básico — deps.py

```python
# backend/app/deps.py
from fastapi import Depends, Request
from app.services.chat_service import ChatService
from app.agent.graph import AgentGraph

# --- DB Pool (criado no lifespan, lido do app.state) ---
async def get_db(request: Request):
    return request.app.state.db_pool

# --- Config (singleton imutável) ---
from app.config import Settings
_settings: Settings | None = None

def get_settings() -> Settings:
    global _settings
    if _settings is None:
        _settings = Settings()
    return _settings

# --- Service com suas dependências ---
async def get_chat_service(
    db=Depends(get_db),
    settings: Settings = Depends(get_settings),
) -> ChatService:
    graph = AgentGraph(db=db, settings=settings)
    return ChatService(graph=graph)
```

## Config com Pydantic Settings

```python
# backend/app/config.py
from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")

    # Banco
    database_url: str
    db_pool_size: int = 10

    # LLM
    openai_api_key: str
    llm_model: str = "gpt-4o"

    # Qdrant
    qdrant_url: str = "http://localhost:6333"

    # App
    debug: bool = False
    cors_origins: list[str] = ["http://localhost:5173"]
```

## Dependency de autenticação

```python
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
import jwt

security = HTTPBearer()

async def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(security),
    settings: Settings = Depends(get_settings),
) -> dict:
    try:
        payload = jwt.decode(
            credentials.credentials,
            settings.jwt_secret,
            algorithms=["HS256"],
        )
        return payload
    except jwt.InvalidTokenError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token inválido ou expirado",
        )

# Uso no router:
@router.post("/protected")
async def protected_route(user: dict = Depends(get_current_user)):
    return {"user_id": user["sub"]}
```

## Dependency com yield — recursos com cleanup

```python
from typing import AsyncGenerator
import asyncpg

async def get_db_conn(
    request: Request,
) -> AsyncGenerator[asyncpg.Connection, None]:
    """Conexão individual do pool — liberada após o request."""
    async with request.app.state.db_pool.acquire() as conn:
        yield conn  # disponível durante o request
        # após o yield: conexão devolvida ao pool automaticamente
```

## Testes com override

```python
# tests/conftest.py
import pytest
from fastapi.testclient import TestClient
from app.main import app
from app.deps import get_chat_service
from unittest.mock import AsyncMock

@pytest.fixture
def client():
    mock_service = AsyncMock()
    mock_service.process.return_value = ServiceResult(answer="mock answer")

    # Override da dependência para o escopo do teste
    app.dependency_overrides[get_chat_service] = lambda: mock_service

    with TestClient(app) as c:
        yield c

    app.dependency_overrides.clear()

def test_chat_endpoint(client):
    resp = client.post("/chat/", json={"query": "teste", "session_id": "s1"})
    assert resp.status_code == 200
    assert resp.json()["answer"] == "mock answer"
```

## Anti-padrões

```python
# ERRADO: global mutável
db_pool = None  # inicializado em algum lugar no startup

@router.post("/chat")
async def chat(body: ChatRequest):
    global db_pool  # acesso direto ao global — injetável, não testável
    rows = await db_pool.fetch("...")

# ERRADO: instanciar serviço dentro da rota
@router.post("/chat")
async def chat(body: ChatRequest):
    service = ChatService()  # sem injeção — mock impossível
    return await service.process(body.query)
```
