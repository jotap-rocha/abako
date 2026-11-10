"""Contas do usuário. Leitura pelas views/tabelas, escrita só pela função `conta_gravar`
(migração 0005, ADR 042); toda chamada usa o `user_id` da sessão (INV-13)."""

from __future__ import annotations

from dataclasses import dataclass

import psycopg


@dataclass(frozen=True)
class Conta:
    conta_id: int
    nome: str
    conta_beneficio: bool
    tipo: str
    conta_mae_id: int | None
    versao: int


_SELECT = (
    "SELECT conta_id, nome, conta_beneficio, tipo, conta_mae_id, versao FROM conta_versao "
    "WHERE user_id = %s AND vigente AND NOT excluida"
)


async def listar(conn: psycopg.AsyncConnection, user_id: int) -> list[Conta]:
    cur = await conn.execute(_SELECT + " ORDER BY conta_id", (user_id,))
    return [Conta(*linha) for linha in await cur.fetchall()]


async def obter(conn: psycopg.AsyncConnection, user_id: int, conta_id: int) -> Conta | None:
    cur = await conn.execute(_SELECT + " AND conta_id = %s", (user_id, conta_id))
    linha = await cur.fetchone()
    return Conta(*linha) if linha else None


async def gravar(
    conn: psycopg.AsyncConnection,
    user_id: int,
    *,
    nome: str,
    tipo: str,
    conta_mae_id: int | None,
    conta_id: int | None = None,
    versao: int | None = None,
) -> int:
    """Cria (sem `conta_id`) ou edita (com a `versao` lida). Devolve o `conta_id`.

    Erros de regra saem como `psycopg.Error` com SQLSTATE AB*** (ver `backend.erros_banco`).
    """
    cur = await conn.execute(
        "SELECT conta_id FROM conta_gravar(%s, %s, %s, %s, %s, %s)",
        (user_id, conta_id, versao, nome, tipo, conta_mae_id),
    )
    linha = await cur.fetchone()
    if linha is None:
        raise RuntimeError("conta_gravar não devolveu linha")
    return int(linha[0])
