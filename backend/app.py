"""Fábrica da aplicação FastAPI: Host, CORS, Origin, cabeçalhos de segurança (ADR 020/031/035)."""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from pathlib import Path

from fastapi import FastAPI, HTTPException, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from fastapi.routing import APIRoute
from starlette.middleware.trustedhost import TrustedHostMiddleware

from backend.routers import auth, contas, saldos
from backend.seguranca import LimitadorLogin
from backend.settings import Settings, obter_settings

METODOS_SEGUROS = {"GET", "HEAD", "OPTIONS"}
# Sem 'unsafe-inline': a SPA servida pelo próprio FastAPI não precisa de script/estilo inline.
CSP = (
    "default-src 'self'; script-src 'self'; style-src 'self'; img-src 'self' data:; "
    "connect-src 'self'; object-src 'none'; base-uri 'none'; form-action 'self'; "
    "frame-ancestors 'none'"
)


def _id_operacao(rota: APIRoute) -> str:
    """`auth_login`, `contas_listar`: nomes curtos e estáveis para as funções do cliente TS."""
    return f"{rota.tags[0]}_{rota.name}" if rota.tags else rota.name


def criar_app(settings: Settings | None = None) -> FastAPI:
    cfg = settings or obter_settings()
    # Sem /docs e /redoc: dependem de CDN, que a CSP bloquearia. O contrato fica em
    # /api/openapi.json (fonte do cliente TS). Tudo da API vive sob /api; o resto é a SPA.
    app = FastAPI(
        title="abako",
        docs_url=None,
        redoc_url=None,
        openapi_url="/api/openapi.json",
        generate_unique_id_function=_id_operacao,
    )
    app.state.settings = cfg
    app.state.limitador = LimitadorLogin(cfg.login_max_falhas, cfg.login_janela_s)
    origens = set(cfg.origens)

    @app.middleware("http")
    async def checar_origin(
        request: Request, call_next: Callable[[Request], Awaitable[Response]]
    ) -> Response:
        """Escrita só de origem conhecida; ausente também é recusada (navegador sempre envia)."""
        if request.method not in METODOS_SEGUROS and request.headers.get("origin") not in origens:
            return JSONResponse({"detail": "origem não permitida"}, status_code=403)
        return await call_next(request)

    app.add_middleware(
        CORSMiddleware,
        allow_origins=list(origens),
        allow_credentials=True,
        allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE"],
        allow_headers=["Content-Type", "X-CSRF-Token"],
    )
    app.add_middleware(TrustedHostMiddleware, allowed_hosts=list(cfg.hosts_permitidos))

    @app.middleware("http")
    async def cabecalhos(
        request: Request, call_next: Callable[[Request], Awaitable[Response]]
    ) -> Response:
        resposta = await call_next(request)
        resposta.headers["Cache-Control"] = "no-store"
        resposta.headers["Content-Security-Policy"] = CSP
        resposta.headers["X-Content-Type-Options"] = "nosniff"
        resposta.headers["Referrer-Policy"] = "no-referrer"
        return resposta

    app.include_router(auth.router, prefix="/api")
    app.include_router(contas.router, prefix="/api")
    app.include_router(saldos.router, prefix="/api")
    _servir_spa(app, cfg.frontend_dist)
    return app


def _servir_spa(app: FastAPI, dist: Path) -> None:
    """Serve o build do front na mesma origem da API (ADR 035). Sem build, a API roda sozinha."""
    indice = dist / "index.html"
    if not indice.is_file():
        return
    raiz = dist.resolve()

    @app.api_route("/{caminho:path}", methods=["GET", "HEAD"], include_in_schema=False)
    async def spa(caminho: str) -> FileResponse:
        if caminho == "api" or caminho.startswith("api/"):
            raise HTTPException(404, "não encontrado")
        try:
            arquivo = (raiz / caminho).resolve()
            # Só arquivos dentro do build (bloqueia ../); qualquer outra rota é da SPA.
            if caminho and arquivo.is_file() and raiz in arquivo.parents:
                return FileResponse(arquivo)
        except (ValueError, OSError):
            pass  # caminho impossível no sistema de arquivos (ex.: byte NUL): é rota da SPA
        return FileResponse(indice)
