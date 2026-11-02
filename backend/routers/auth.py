"""Login, logout e identidade da sessão. Fino: valida, delega ao service, formata."""

from __future__ import annotations

import logging

import anyio.to_thread
from fastapi import APIRouter, HTTPException, Request, Response, status
from pydantic import BaseModel, Field

from backend.deps import COOKIE_SESSAO, Conexao, Sessao, SessaoEscrita
from backend.seguranca import senha_confere
from backend.services import sessao as svc_sessao

log = logging.getLogger("abako.auth")
router = APIRouter(prefix="/auth", tags=["auth"])


class LoginEntrada(BaseModel):
    login: str = Field(min_length=1, max_length=64)
    senha: str = Field(min_length=1, max_length=1024)


class LoginSaida(BaseModel):
    csrf_token: str


@router.post("/login", response_model=LoginSaida)
async def login(
    entrada: LoginEntrada, request: Request, response: Response, conn: Conexao
) -> LoginSaida:
    cfg = request.app.state.settings
    limitador = request.app.state.limitador
    chave = entrada.login.strip().lower()
    espera = limitador.espera_s(chave)
    if espera:
        log.warning("login bloqueado por excesso de tentativas")
        raise HTTPException(
            status.HTTP_429_TOO_MANY_REQUESTS,
            "tentativas demais; tente mais tarde",
            headers={"Retry-After": str(espera)},
        )
    # Reserva a tentativa antes do Argon2: rajadas paralelas não furam o limite.
    limitador.registrar_falha(chave)
    cred = await svc_sessao.buscar_credencial(conn, chave)
    # Argon2 é CPU-bound: fora do event loop.
    ok = await anyio.to_thread.run_sync(senha_confere, cred[1] if cred else None, entrada.senha)
    if not ok or cred is None:
        log.info("login recusado")
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "login ou senha inválidos")
    limitador.limpar(chave)
    token, csrf = await svc_sessao.criar(conn, cred[0], cfg.sessao_duracao_s)
    # Commit antes de responder: o cookie não pode chegar antes da sessão existir.
    await conn.commit()
    response.set_cookie(
        COOKIE_SESSAO,
        token,
        max_age=cfg.sessao_duracao_s,
        httponly=True,
        samesite="strict",
        path="/",
    )
    log.info("login aceito")
    return LoginSaida(csrf_token=csrf)


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
async def logout(request: Request, response: Response, conn: Conexao, _: SessaoEscrita) -> None:
    token = request.cookies.get(COOKIE_SESSAO)
    if token:
        await svc_sessao.encerrar(conn, token)
        await conn.commit()
    response.delete_cookie(COOKIE_SESSAO, path="/")


@router.get("/eu", response_model=LoginSaida)
async def eu(sessao: Sessao) -> LoginSaida:
    """Reentrega o token CSRF à página recarregada, sem expor o `user_id`."""
    return LoginSaida(csrf_token=sessao.csrf_token)
