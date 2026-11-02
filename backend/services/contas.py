"""Leitura de contas vigentes; toda consulta filtra pelo `user_id` da sessão (INV-13)."""

from __future__ import annotations

from dataclasses import dataclass

import psycopg


@dataclass(frozen=True)
class Conta:
    conta_id: int
    nome: str
    conta_beneficio: bool


_SELECT = (
    "SELECT conta_id, nome, conta_beneficio FROM conta_versao "
    "WHERE user_id = %s AND vigente AND NOT excluida"
)


async def listar(conn: psycopg.AsyncConnection, user_id: int) -> list[Conta]:
    cur = await conn.execute(_SELECT + " ORDER BY conta_id", (user_id,))
    return [Conta(*linha) for linha in await cur.fetchall()]


async def obter(conn: psycopg.AsyncConnection, user_id: int, conta_id: int) -> Conta | None:
    cur = await conn.execute(_SELECT + " AND conta_id = %s", (user_id, conta_id))
    linha = await cur.fetchone()
    return Conta(*linha) if linha else None
