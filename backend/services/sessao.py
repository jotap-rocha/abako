"""Sessão no servidor (Postgres): cria, resolve pelo cookie e encerra."""

from __future__ import annotations

from dataclasses import dataclass

import psycopg

from backend.seguranca import hash_token, novo_token


@dataclass(frozen=True)
class SessaoAtiva:
    user_id: int
    csrf_token: str


async def buscar_credencial(conn: psycopg.AsyncConnection, login: str) -> tuple[int, str] | None:
    cur = await conn.execute(
        "SELECT u.user_id, c.senha_hash FROM usuario u "
        "JOIN credencial c USING (user_id) WHERE u.login = %s",
        (login,),
    )
    linha = await cur.fetchone()
    return (linha[0], linha[1]) if linha else None


async def criar(conn: psycopg.AsyncConnection, user_id: int, duracao_s: int) -> tuple[str, str]:
    """Devolve (token do cookie, token CSRF); no banco fica só o hash do primeiro."""
    token, csrf = novo_token(), novo_token()
    await conn.execute("DELETE FROM sessao WHERE expira_em <= now()")
    await conn.execute(
        "INSERT INTO sessao (user_id, token_hash, csrf_token, expira_em) "
        "VALUES (%s, %s, %s, now() + make_interval(secs => %s))",
        (user_id, hash_token(token), csrf, duracao_s),
    )
    return token, csrf


async def resolver(conn: psycopg.AsyncConnection, token: str) -> SessaoAtiva | None:
    cur = await conn.execute(
        "SELECT user_id, csrf_token FROM sessao WHERE token_hash = %s AND expira_em > now()",
        (hash_token(token),),
    )
    linha = await cur.fetchone()
    return SessaoAtiva(user_id=linha[0], csrf_token=linha[1]) if linha else None


async def encerrar(conn: psycopg.AsyncConnection, token: str) -> None:
    await conn.execute("DELETE FROM sessao WHERE token_hash = %s", (hash_token(token),))
    # Aproveita para varrer sessões vencidas.
    await conn.execute("DELETE FROM sessao WHERE expira_em <= now()")
