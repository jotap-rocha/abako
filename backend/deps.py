"""Dependências: o `user_id` vem sempre da sessão (cookie), nunca do corpo (INV-13)."""

from __future__ import annotations

from typing import Annotated

import psycopg
from fastapi import Depends, Header, HTTPException, Request, status

from backend.db import conexao
from backend.seguranca import tokens_iguais
from backend.services import sessao as svc_sessao

COOKIE_SESSAO = "abako_sessao"
Conexao = Annotated[psycopg.AsyncConnection, Depends(conexao)]


async def sessao_atual(request: Request, conn: Conexao) -> svc_sessao.SessaoAtiva:
    token = request.cookies.get(COOKIE_SESSAO)
    ativa = await svc_sessao.resolver(conn, token) if token else None
    if ativa is None:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "não autenticado")
    return ativa


Sessao = Annotated[svc_sessao.SessaoAtiva, Depends(sessao_atual)]


async def sessao_csrf(
    sessao: Sessao, x_csrf_token: Annotated[str | None, Header()] = None
) -> svc_sessao.SessaoAtiva:
    """Exigida em toda escrita autenticada: o cabeçalho deve repetir o token da sessão."""
    if not x_csrf_token or not tokens_iguais(x_csrf_token, sessao.csrf_token):
        raise HTTPException(status.HTTP_403_FORBIDDEN, "token CSRF ausente ou inválido")
    return sessao


SessaoEscrita = Annotated[svc_sessao.SessaoAtiva, Depends(sessao_csrf)]
