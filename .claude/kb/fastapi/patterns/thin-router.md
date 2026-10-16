# Padrão Router Fino (Thin Router)

## Regra: router tem exatamente 3 responsabilidades

1. Declarar o endpoint (método, path, schemas, status code)
2. Chamar o service
3. Mapear erros de domínio para HTTP

```python
# backend/app/routers/chat.py
from fastapi import APIRouter, Depends, HTTPException, status
from app.schemas.chat import ChatRequest, ChatResponse
from app.services.chat_service import ChatService
from app.deps import get_chat_service
from app.exceptions import NotFoundError, ValidationDomainError

router = APIRouter(prefix="/chat", tags=["Chat"])

@router.post(
    "/",
    response_model=ChatResponse,
    status_code=status.HTTP_200_OK,
    summary="Processa query analítica",
)
async def chat(
    body: ChatRequest,
    service: ChatService = Depends(get_chat_service),
) -> ChatResponse:
    try:
        result = await service.process(body.query, body.session_id)
    except ValidationDomainError as e:
        raise HTTPException(status_code=422, detail=e.message)
    except Exception:
        raise HTTPException(status_code=500, detail="Erro interno")

    return ChatResponse(answer=result.answer, sources=result.sources)
```

## Template para CRUD

```python
router = APIRouter(prefix="/produtos", tags=["Produtos"])

@router.get("/", response_model=list[ProductResponse])
async def list_products(
    category: str | None = None,
    limit: int = 50,
    service=Depends(get_product_service),
):
    return await service.list(category=category, limit=min(limit, 200))

@router.get("/{product_id}", response_model=ProductResponse)
async def get_product(product_id: str, service=Depends(get_product_service)):
    try:
        return await service.get(product_id)
    except NotFoundError:
        raise HTTPException(status_code=404, detail="Produto não encontrado")

@router.post("/", response_model=ProductResponse, status_code=201)
async def create_product(body: ProductCreate, service=Depends(get_product_service)):
    return await service.create(body)
```

## Montagem no main.py

```python
from fastapi import FastAPI
from app.routers import chat, health, produtos

app = FastAPI(title="API Analítica", version="1.0.0")

# Prefixo global de versão
app.include_router(chat.router,    prefix="/v1")
app.include_router(health.router,  prefix="/v1")
app.include_router(produtos.router, prefix="/v1")
```

## O que o router NÃO deve conter

```python
# ERRADO: SQL direto no router
@router.get("/produtos")
async def list_products(db=Depends(get_db)):
    rows = await db.fetch("SELECT * FROM produtos")  # lógica no router!
    return rows

# ERRADO: LLM no router
@router.post("/chat")
async def chat(body: ChatRequest):
    response = openai.chat.completions.create(...)  # chamada LLM no router!
    return {"answer": response.choices[0].message.content}

# ERRADO: lógica de negócio no router
@router.post("/pedido")
async def create_order(body: OrderRequest):
    if body.amount > 10000:          # regra de negócio no router!
        send_fraud_alert(body)
    ...
```

## Checklist de router fino

- [ ] Cada endpoint cabe em menos de 15 linhas
- [ ] Nenhuma lógica além de: chamar service + mapear erros
- [ ] `response_model` declarado em todo endpoint
- [ ] Sem acesso direto a DB, LLM, Qdrant — tudo via service
- [ ] Sem `if/else` de negócio — só `try/except` de erros de domínio
