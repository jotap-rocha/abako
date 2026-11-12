"""Recorrentes, ocorrências e vínculo com transação (SPEC-010, ADR 048).

A regra (ocorrência derivada, último dia válido, valor esperado x valor da transação, vínculo
efetivo, versionamento) vive nas funções e views da migração 0011; aqui só se monta a chamada,
sempre com o `user_id` da sessão (INV-13). Nenhum cálculo financeiro em Python. O nome do
recorrente e os valores nunca vão a log nem a mensagem de erro.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from decimal import Decimal

import psycopg

COLUNAS_OCORRENCIA = (
    "recorrente_id, nome, tipo, conta_id, mes, data, valor_esperado, valor, transacao_id, vinculada"
)


@dataclass(frozen=True)
class Recorrente:
    recorrente_id: int
    nome: str
    tipo: str
    valor: Decimal
    dia: int
    conta_id: int
    mes_inicio: str
    mes_fim: str | None
    versao: int


@dataclass(frozen=True)
class Ocorrencia:
    recorrente_id: int
    nome: str
    tipo: str
    conta_id: int
    mes: str
    data: date
    valor_esperado: Decimal
    valor: Decimal
    transacao_id: int | None
    vinculada: bool


# Os meses saem como AAAA-MM direto do banco (formatação, não regra).
_SELECT = (
    "SELECT recorrente_id, nome, tipo, valor, dia, conta_id, "
    "to_char(mes_inicio::timestamp, 'YYYY-MM'), "
    "to_char(mes_fim::timestamp, 'YYYY-MM'), versao "
    "FROM recorrente_vigente WHERE user_id = %s"
)


async def listar(conn: psycopg.AsyncConnection, user_id: int) -> list[Recorrente]:
    cur = await conn.execute(_SELECT + " ORDER BY lower(nome), recorrente_id", (user_id,))
    return [Recorrente(*linha) for linha in await cur.fetchall()]


async def obter(
    conn: psycopg.AsyncConnection, user_id: int, recorrente_id: int
) -> Recorrente | None:
    cur = await conn.execute(_SELECT + " AND recorrente_id = %s", (user_id, recorrente_id))
    linha = await cur.fetchone()
    return Recorrente(*linha) if linha else None


async def gravar(
    conn: psycopg.AsyncConnection,
    user_id: int,
    *,
    nome: str,
    tipo: str,
    valor: Decimal,
    dia: int,
    conta_id: int,
    mes_inicio: str,
    mes_fim: str | None,
    recorrente_id: int | None = None,
    versao: int | None = None,
) -> int:
    """Cria (sem `recorrente_id`) ou edita (com a `versao` lida). Erros de regra: AB***."""
    cur = await conn.execute(
        "SELECT recorrente_id FROM recorrente_gravar(%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)",
        (user_id, recorrente_id, versao, nome, tipo, valor, dia, conta_id, mes_inicio, mes_fim),
    )
    linha = await cur.fetchone()
    if linha is None:
        raise RuntimeError("recorrente_gravar não devolveu linha")
    return int(linha[0])


async def excluir(
    conn: psycopg.AsyncConnection, user_id: int, recorrente_id: int, versao: int
) -> None:
    await conn.execute("SELECT recorrente_excluir(%s, %s, %s)", (user_id, recorrente_id, versao))


async def ocorrencias_do_mes(
    conn: psycopg.AsyncConnection,
    user_id: int,
    mes: str,
    recorrente_id: int | None = None,
) -> list[Ocorrencia]:
    cur = await conn.execute(
        f"SELECT {COLUNAS_OCORRENCIA} FROM ocorrencias_do_mes(%s, %s) "  # noqa: S608
        "WHERE (%s::bigint IS NULL OR recorrente_id = %s::bigint)",
        (user_id, mes, recorrente_id, recorrente_id),
    )
    return [Ocorrencia(*linha) for linha in await cur.fetchall()]


async def vincular(
    conn: psycopg.AsyncConnection, user_id: int, recorrente_id: int, mes: str, transacao_id: int
) -> None:
    await conn.execute(
        "SELECT recorrente_vincular(%s, %s, %s, %s)", (user_id, recorrente_id, mes, transacao_id)
    )


async def desvincular(
    conn: psycopg.AsyncConnection, user_id: int, recorrente_id: int, mes: str
) -> None:
    await conn.execute("SELECT recorrente_desvincular(%s, %s, %s)", (user_id, recorrente_id, mes))
