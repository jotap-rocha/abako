# Router vs Service Layer

## A separação

**Router** = contrato HTTP. Valida entrada, chama service, retorna saída. Sem lógica.
**Service** = lógica de negócio. Não sabe que existe HTTP. Testável sem cliente HTTP.

```
Request → Router (validação + schema) → Service (lógica) → Router (response_model)
```

## Router — o que pode e o que não pode

```python
# backend/app/routers/chat.py
from fastapi import APIRouter, Depends, HTTPException, status
from app.schemas.chat import ChatRequest, ChatResponse
from app.services.chat_service import ChatService
from app.deps import get_chat_service

router = APIRouter(prefix="/chat", tags=["chat"])

@router.post("/", response_model=ChatResponse, status_code=status.HTTP_200_OK)
async def chat(
    body: ChatRequest,             # Pydantic valida e deserializa
    service: ChatService = Depends(get_chat_service),  # injeção
) -> ChatResponse:
    # PODE: delegar ao service
    result = await service.process(body.query, body.session_id)

    # PODE: mapear erros de domínio para HTTP
    if result.error:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                            detail=result.error)

    # PODE: retornar response schema
    return ChatResponse(answer=result.answer, sources=result.sources)

    # NÃO PODE: lógica de negócio, acesso direto a DB, chamadas LLM
```

## Service — o que pode e o que não pode

```python
# backend/app/services/chat_service.py
from dataclasses import dataclass
from app.agent.graph import AgentGraph
from app.schemas.chat import ServiceResult

@dataclass
class ChatService:
    graph: AgentGraph

    async def process(self, query: str, session_id: str) -> ServiceResult:
        # PODE: lógica de negócio, orquestração, chamadas ao grafo/DB
        result = await self.graph.ainvoke({
            "query": query,
            "session_id": session_id,
        })

        if result.get("error"):
            return ServiceResult(error=result["error"])

        return ServiceResult(
            answer=result["answer"],
            sources=result.get("sources", []),
        )

    # NÃO PODE: raise HTTPException, usar Request/Response do FastAPI
    # NÃO PODE: lógica de validação de schema HTTP (isso é do router)
```

## Schemas — contrato de I/O

```python
# backend/app/schemas/chat.py
from pydantic import BaseModel, Field

class ChatRequest(BaseModel):
    query: str = Field(..., min_length=1, max_length=2000)
    session_id: str = Field(..., min_length=1)

class ChatResponse(BaseModel):
    answer: str
    sources: list[str] = Field(default_factory=list)

class ServiceResult(BaseModel):
    answer: str = ""
    sources: list[str] = Field(default_factory=list)
    error: str | None = None
```

## main.py — montagem do app

```python
# backend/app/main.py
from contextlib import asynccontextmanager
from fastapi import FastAPI
from app.routers import chat, health
from app.db import create_pool, close_pool

@asynccontextmanager
async def lifespan(app: FastAPI):
    # startup
    app.state.db_pool = await create_pool()
    yield
    # shutdown
    await close_pool(app.state.db_pool)

app = FastAPI(title="Agente Analítico", lifespan=lifespan)
app.include_router(chat.router)
app.include_router(health.router)
```

## Testes — service sem HTTP

```python
# backend/tests/test_chat_service.py
import pytest
from unittest.mock import AsyncMock
from app.services.chat_service import ChatService

@pytest.mark.asyncio
async def test_chat_service_returns_answer():
    mock_graph = AsyncMock()
    mock_graph.ainvoke.return_value = {"answer": "42", "sources": ["sql:produtos"]}

    service = ChatService(graph=mock_graph)
    result = await service.process("qual o produto mais vendido?", "sess-1")

    assert result.answer == "42"
    assert result.error is None
    mock_graph.ainvoke.assert_called_once()
```

## Anti-padrões

```python
# ERRADO: lógica de negócio no router
@router.post("/chat")
async def chat(body: ChatRequest, db = Depends(get_db)):
    rows = await db.fetch("SELECT * FROM produtos WHERE ...")  # lógica no router!
    result = llm.invoke(f"Analise: {rows}")                   # LLM no router!
    return {"answer": result}

# ERRADO: HTTPException no service
class BadService:
    async def process(self, query):
        if not query:
            raise HTTPException(status_code=400, detail="...")  # acoplamento HTTP!
```
