# OpenAPI Contract com Pydantic

## Schemas bem declarados — o OpenAPI vira documentação real

```python
# backend/app/schemas/chat.py
from pydantic import BaseModel, Field
from typing import Annotated

class ChatRequest(BaseModel):
    query: Annotated[str, Field(
        min_length=1,
        max_length=2000,
        description="Pergunta em linguagem natural sobre os dados de vendas",
        examples=["Quais produtos mais venderam no último trimestre?"],
    )]
    session_id: Annotated[str, Field(
        min_length=1,
        description="ID da sessão do usuário para rastreamento",
    )]

    model_config = {"json_schema_extra": {
        "example": {
            "query": "Quais produtos mais venderam no último trimestre?",
            "session_id": "user-123-session-abc",
        }
    }}

class SourceRef(BaseModel):
    source: str = Field(description="Identificador da fonte (sql:tabela ou qdrant:coleção:id)")
    score: float | None = Field(None, description="Relevância semântica (0–1), se disponível")

class ChatResponse(BaseModel):
    answer: str = Field(description="Resposta gerada em linguagem natural")
    sources: list[str] = Field(
        default_factory=list,
        description="Fontes consultadas para grounding da resposta",
    )
```

## FastAPI com metadados completos

```python
from fastapi import FastAPI
from fastapi.openapi.utils import get_openapi

app = FastAPI(
    title="Agente Analítico de Vendas",
    description="""
API de análise de vendas com linguagem natural.

## Funcionalidades

- **Chat**: processa queries em linguagem natural e retorna análises fundamentadas
- **Health**: verifica estado das dependências (Postgres, Qdrant)

## Autenticação

Bearer token JWT no header `Authorization`.
    """,
    version="1.0.0",
    contact={"name": "Time de Dados", "email": "dados@empresa.com"},
    license_info={"name": "Privado"},
    openapi_tags=[
        {"name": "Chat", "description": "Processamento de queries analíticas"},
        {"name": "Health", "description": "Verificação de saúde da API"},
    ],
)
```

## Endpoint com contrato completo

```python
from fastapi import APIRouter, Depends, HTTPException, status
from app.schemas.chat import ChatRequest, ChatResponse
from app.schemas.error import ErrorResponse

router = APIRouter()

@router.post(
    "/chat",
    response_model=ChatResponse,
    status_code=status.HTTP_200_OK,
    summary="Processa uma query analítica",
    description="""
Recebe uma pergunta em linguagem natural e retorna análise
com dados fundamentados e fontes citadas.

**Exemplos de queries válidas:**
- "Quais produtos mais venderam no Q3?"
- "Compare o desempenho por região"
- "Quais metas foram batidas em outubro?"
    """,
    responses={
        200: {"description": "Resposta gerada com sucesso"},
        422: {"model": ErrorResponse, "description": "Input inválido"},
        504: {"description": "Timeout do LLM ou banco de dados"},
    },
    tags=["Chat"],
)
async def chat(body: ChatRequest, service=Depends(get_chat_service)) -> ChatResponse:
    ...
```

## Enum para campos com valores fixos

```python
from enum import Enum

class IntentType(str, Enum):
    SQL_AGGREGATE = "sql_aggregate"
    SQL_LOOKUP    = "sql_lookup"
    DOC_SEARCH    = "doc_search"
    HYBRID        = "hybrid"
    OUT_OF_SCOPE  = "out_of_scope"

class DebugResponse(BaseModel):
    intent: IntentType
    confidence: float = Field(ge=0.0, le=1.0)
    entities: list[str]
```

## Exportar schema para validação CI

```bash
# Gerar openapi.json para versionar e comparar em PRs
uvx --from fastapi-cli fastapi run backend/app/main.py &
sleep 2
curl http://localhost:8000/openapi.json > openapi.json
kill %1
```

## Regras de contrato OpenAPI

| # | Regra |
|---|---|
| OA-01 | Todo endpoint tem `response_model` — sem `dict` como retorno |
| OA-02 | Todo campo tem `description` no `Field()` |
| OA-03 | `responses` documenta pelo menos os casos de erro (422, 500) |
| OA-04 | `model_config` com `json_schema_extra.example` nos schemas de request |
| OA-05 | Enums para campos com valores fixos — não `str` livre |
| OA-06 | `openapi.json` versionado — quebrar contrato exige ADR |
