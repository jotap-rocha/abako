# Error Contracts no FastAPI

## Schema de erro padronizado

Toda API deve retornar erros no mesmo formato — não strings brutas.

```python
# backend/app/schemas/error.py
from pydantic import BaseModel

class ErrorDetail(BaseModel):
    code: str        # "VALIDATION_ERROR", "NOT_FOUND", "INTERNAL_ERROR"
    message: str     # mensagem legível para o frontend
    field: str | None = None  # campo com problema (para validação)

class ErrorResponse(BaseModel):
    error: ErrorDetail
    request_id: str | None = None  # para correlação de logs
```

## Handler global de exceções

```python
# backend/app/main.py
from fastapi import FastAPI, Request, status
from fastapi.responses import JSONResponse
from fastapi.exceptions import RequestValidationError
from app.schemas.error import ErrorResponse, ErrorDetail
import uuid

app = FastAPI()

@app.exception_handler(RequestValidationError)
async def validation_error_handler(request: Request, exc: RequestValidationError):
    errors = exc.errors()
    first = errors[0] if errors else {}
    return JSONResponse(
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        content=ErrorResponse(
            error=ErrorDetail(
                code="VALIDATION_ERROR",
                message=first.get("msg", "Dados inválidos"),
                field=".".join(str(l) for l in first.get("loc", [])),
            )
        ).model_dump(),
    )

@app.exception_handler(Exception)
async def generic_error_handler(request: Request, exc: Exception):
    request_id = str(uuid.uuid4())
    # logar com request_id para correlação
    logger.error(f"[{request_id}] Erro não tratado: {exc}", exc_info=True)
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content=ErrorResponse(
            error=ErrorDetail(code="INTERNAL_ERROR", message="Erro interno"),
            request_id=request_id,
        ).model_dump(),
    )
```

## Exceções de domínio → HTTPException no router

```python
# backend/app/exceptions.py
class DomainError(Exception):
    """Base para erros de domínio — não sabe que existe HTTP."""
    def __init__(self, code: str, message: str):
        self.code = code
        self.message = message

class NotFoundError(DomainError):
    pass

class ValidationDomainError(DomainError):
    pass

# No service — lança DomainError
class ProductService:
    async def get(self, product_id: str) -> Product:
        product = await self.db.fetch_one("SELECT * FROM produtos WHERE id = $1", product_id)
        if not product:
            raise NotFoundError("PRODUCT_NOT_FOUND", f"Produto {product_id} não encontrado")
        return Product(**product)

# No router — converte para HTTP
from fastapi import HTTPException, status

@router.get("/{product_id}", response_model=ProductResponse)
async def get_product(product_id: str, service=Depends(get_product_service)):
    try:
        product = await service.get(product_id)
        return ProductResponse.model_validate(product)
    except NotFoundError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=e.message)
    except ValidationDomainError as e:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=e.message)
```

## responses declarados no OpenAPI

```python
from fastapi import APIRouter
from app.schemas.chat import ChatRequest, ChatResponse
from app.schemas.error import ErrorResponse

router = APIRouter()

@router.post(
    "/chat",
    response_model=ChatResponse,
    status_code=200,
    responses={
        422: {"model": ErrorResponse, "description": "Input inválido"},
        500: {"model": ErrorResponse, "description": "Erro interno"},
        504: {"description": "LLM timeout"},
    },
    summary="Processa uma query analítica",
    description="Recebe query em linguagem natural e retorna análise com fontes.",
)
async def chat(body: ChatRequest, service=Depends(get_chat_service)):
    ...
```

## Tabela de códigos de erro

| Situação | HTTP Status | `code` |
|---|---|---|
| Input inválido (schema) | 422 | `VALIDATION_ERROR` |
| Recurso não encontrado | 404 | `NOT_FOUND` |
| Não autenticado | 401 | `UNAUTHORIZED` |
| Sem permissão | 403 | `FORBIDDEN` |
| Timeout de LLM/DB | 504 | `UPSTREAM_TIMEOUT` |
| Erro interno genérico | 500 | `INTERNAL_ERROR` |
| Rate limit atingido | 429 | `RATE_LIMIT_EXCEEDED` |

## Logging estruturado de erros

```python
import structlog

log = structlog.get_logger()

# Em cada handler de exceção:
log.error(
    "request_error",
    path=request.url.path,
    method=request.method,
    error_code=detail.code,
    request_id=request_id,
    exc_info=True,
)
```
