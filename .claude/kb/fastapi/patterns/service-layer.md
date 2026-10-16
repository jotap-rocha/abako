# Padrão Service Layer

## Estrutura canônica

```python
# backend/app/services/chat_service.py
from dataclasses import dataclass
from app.agent.graph import AgentGraph
from app.schemas.chat import ServiceResult
from app.harness.recorder import HarnessRecorder
import structlog

log = structlog.get_logger(__name__)

@dataclass
class ChatService:
    graph: AgentGraph
    recorder: HarnessRecorder

    async def process(self, query: str, session_id: str) -> ServiceResult:
        log.info("chat.start", session_id=session_id, query_len=len(query))

        try:
            raw = await self.graph.ainvoke({
                "query": query,
                "session_id": session_id,
                "intent": "",
                "sql_result": "",
                "search_result": "",
                "sources": [],
                "answer": "",
                "error": None,
            })
        except Exception as e:
            log.error("chat.graph_error", session_id=session_id, error=str(e))
            return ServiceResult(error="Falha ao processar a query")

        if raw.get("error"):
            log.warning("chat.domain_error", session_id=session_id, error=raw["error"])
            return ServiceResult(error=raw["error"])

        await self.recorder.record(
            session_id=session_id,
            query=query,
            answer=raw["answer"],
            sources=raw.get("sources", []),
        )

        log.info("chat.done", session_id=session_id)
        return ServiceResult(answer=raw["answer"], sources=raw.get("sources", []))
```

## Injeção das dependências do service

```python
# backend/app/deps.py
from fastapi import Depends, Request
from app.services.chat_service import ChatService
from app.agent.graph import AgentGraph
from app.harness.recorder import HarnessRecorder

async def get_chat_service(request: Request) -> ChatService:
    graph = AgentGraph(
        db_pool=request.app.state.db_pool,
        qdrant=request.app.state.qdrant,
        settings=request.app.state.settings,
    )
    recorder = HarnessRecorder(db_pool=request.app.state.db_pool)
    return ChatService(graph=graph, recorder=recorder)
```

## Service para CRUD (com DB direto)

```python
# backend/app/services/product_service.py
from dataclasses import dataclass
import asyncpg
from app.schemas.produto import Product, ProductCreate
from app.exceptions import NotFoundError

@dataclass
class ProductService:
    db: asyncpg.Pool

    async def list(self, category: str | None = None, limit: int = 50) -> list[Product]:
        query = "SELECT * FROM produtos"
        params = []
        if category:
            query += " WHERE categoria = $1"
            params.append(category)
        query += f" LIMIT {min(limit, 200)}"

        async with self.db.acquire() as conn:
            rows = await conn.fetch(query, *params)
        return [Product(**dict(r)) for r in rows]

    async def get(self, product_id: str) -> Product:
        async with self.db.acquire() as conn:
            row = await conn.fetchrow(
                "SELECT * FROM produtos WHERE id = $1", product_id
            )
        if not row:
            raise NotFoundError("PRODUCT_NOT_FOUND", f"Produto {product_id} não encontrado")
        return Product(**dict(row))
```

## Teste do service sem HTTP

```python
# tests/services/test_chat_service.py
import pytest
from unittest.mock import AsyncMock, MagicMock
from app.services.chat_service import ChatService

@pytest.fixture
def chat_service():
    mock_graph = AsyncMock()
    mock_recorder = AsyncMock()
    return ChatService(graph=mock_graph, recorder=mock_recorder)

@pytest.mark.asyncio
async def test_returns_answer_on_success(chat_service):
    chat_service.graph.ainvoke.return_value = {
        "answer": "Produto X foi o mais vendido",
        "sources": ["sql:negocio.pedidos"],
        "error": None,
    }
    result = await chat_service.process("qual o mais vendido?", "sess-1")
    assert result.answer == "Produto X foi o mais vendido"
    assert result.error is None

@pytest.mark.asyncio
async def test_returns_error_on_graph_failure(chat_service):
    chat_service.graph.ainvoke.side_effect = Exception("timeout")
    result = await chat_service.process("...", "sess-1")
    assert result.error is not None
    assert result.answer == ""
```

## Regras do service layer

| # | Regra |
|---|---|
| SL-01 | Sem `HTTPException` — lança `DomainError` ou retorna `ServiceResult(error=...)` |
| SL-02 | Sem `Request`/`Response` do FastAPI — desacoplado do protocolo HTTP |
| SL-03 | Logging estruturado em cada operação relevante |
| SL-04 | Toda dependência injetada via `__init__` ou `dataclass` — não importada como global |
| SL-05 | Testável sem subir o servidor HTTP |
