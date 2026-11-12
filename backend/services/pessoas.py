"""Pessoas (terceiros) e "a receber" por pessoa (SPEC-007, ADR 045).

A regra (D, R, a receber, crédito da pessoa, exclusão recusada com movimento) vive nas funções da
migração 0008; aqui só se monta a chamada, sempre com o `user_id` da sessão (INV-13). O nome é
dado pessoal: nunca vai a log nem a mensagem de erro.
"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal

import psycopg


@dataclass(frozen=True)
class Pessoa:
    pessoa_id: int
    nome: str
    versao: int


@dataclass(frozen=True)
class AReceber:
    pessoa_id: int
    nome: str
    divida: Decimal
    repassado: Decimal
    a_receber: Decimal
    credito_da_pessoa: Decimal


_SELECT = (
    "SELECT pessoa_id, nome, versao FROM pessoa WHERE user_id = %s AND vigente AND NOT excluida"
)


async def listar(conn: psycopg.AsyncConnection, user_id: int) -> list[Pessoa]:
    cur = await conn.execute(_SELECT + " ORDER BY lower(nome), pessoa_id", (user_id,))
    return [Pessoa(*linha) for linha in await cur.fetchall()]


async def obter(conn: psycopg.AsyncConnection, user_id: int, pessoa_id: int) -> Pessoa | None:
    cur = await conn.execute(_SELECT + " AND pessoa_id = %s", (user_id, pessoa_id))
    linha = await cur.fetchone()
    return Pessoa(*linha) if linha else None


async def gravar(
    conn: psycopg.AsyncConnection,
    user_id: int,
    *,
    nome: str,
    pessoa_id: int | None = None,
    versao: int | None = None,
) -> int:
    """Cria (sem `pessoa_id`) ou renomeia (com a `versao` lida). Erros de regra: SQLSTATE AB***."""
    cur = await conn.execute(
        "SELECT pessoa_id FROM pessoa_gravar(%s, %s, %s, %s)", (user_id, pessoa_id, versao, nome)
    )
    linha = await cur.fetchone()
    if linha is None:
        raise RuntimeError("pessoa_gravar não devolveu linha")
    return int(linha[0])


async def excluir(conn: psycopg.AsyncConnection, user_id: int, pessoa_id: int, versao: int) -> None:
    await conn.execute("SELECT pessoa_excluir(%s, %s, %s)", (user_id, pessoa_id, versao))


async def a_receber(
    conn: psycopg.AsyncConnection, user_id: int, pessoa_id: int | None = None
) -> list[AReceber]:
    """Uma linha por pessoa vigente. O nome é resolvido aqui, na borda, por usuário."""
    cur = await conn.execute(
        "SELECT r.pessoa_id, p.nome, r.divida, r.repassado, r.a_receber, r.credito_da_pessoa "
        "FROM a_receber_pessoas(%s, %s) r "
        "JOIN pessoa p ON p.user_id = %s AND p.pessoa_id = r.pessoa_id "
        "AND p.vigente AND NOT p.excluida "
        "ORDER BY lower(p.nome), r.pessoa_id",
        (user_id, pessoa_id, user_id),
    )
    return [AReceber(*linha) for linha in await cur.fetchall()]
