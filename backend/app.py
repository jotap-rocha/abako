"""Fábrica da aplicação FastAPI: Host, CORS, Origin, cabeçalhos de segurança (ADR 020/031/035)."""

from __future__ import annotations

from collections.abc import Awaitable, Callable

from fastapi import FastAPI, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from starlette.middleware.trustedhost import TrustedHostMiddleware

from backend.routers import auth, contas
from backend.seguranca import LimitadorLogin
from backend.settings import Settings, obter_settings

METODOS_SEGUROS = {"GET", "HEAD", "OPTIONS"}
# Sem 'unsafe-inline': a SPA servida pelo próprio FastAPI não precisa de script/estilo inline.
CSP = (
    "default-src 'self'; script-src 'self'; style-src 'self'; img-src 'self' data:; "
    "connect-src 'self'; object-src 'none'; base-uri 'none'; form-action 'self'; "
    "frame-ancestors 'none'"
)


def criar_app(settings: Settings | None = None) -> FastAPI:
    cfg = settings or obter_settings()
    # Sem /docs e /redoc: dependem de CDN, que a CSP bloquearia. O /openapi.json fica.
    app = FastAPI(title="abako", docs_url=None, redoc_url=None)
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

    app.include_router(auth.router)
    app.include_router(contas.router)
    return app
