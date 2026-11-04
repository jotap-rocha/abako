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


async def criar_conta(
    conn: psycopg.AsyncConnection, user_id: int, nome: str, conta_beneficio: bool
) -> Conta | None:
    """Cria a conta; devolve None se o usuário já tem uma conta vigente com esse nome."""
    cur = await conn.execute(
        "SELECT 1 FROM conta_versao WHERE user_id = %s AND vigente AND NOT excluida "
        "AND lower(nome) = lower(%s)",
        (user_id, nome),
    )
    if await cur.fetchone() is not None:
        return None
    try:
        cur = await conn.execute(
            "INSERT INTO conta_versao (user_id, nome, conta_beneficio) VALUES (%s, %s, %s) "
            "RETURNING conta_id, nome, conta_beneficio",
            (user_id, nome, conta_beneficio),
        )
    except psycopg.errors.UniqueViolation:
        await conn.rollback()  # outra requisição criou o mesmo nome entre a checagem e o insert
        return None
    linha = await cur.fetchone()
    assert linha is not None
    return Conta(*linha)
