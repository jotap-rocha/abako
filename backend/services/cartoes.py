"""Linha de crédito, fechamento do cartão, fatura e limite (SPEC-005, ADR 043).

A regra (competência, parcelas, limite usado) vive nas funções da migração 0006; aqui só se monta
a chamada, sempre com o `user_id` da sessão (INV-13).
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from decimal import Decimal

import psycopg


@dataclass(frozen=True)
class Linha:
    linha_id: int
    nome: str
    limite: Decimal
    versao: int


@dataclass(frozen=True)
class Fechamento:
    dia: int
    vigente_desde: date


@dataclass(frozen=True)
class ItemFatura:
    transacao_id: int
    versao: int
    parcela: int
    parcelas: int
    data_compra: date
    valor: Decimal
    descricao: str | None
    # Nula = compra própria (ou crédito de estorno de compra própria).
    pessoa_id: int | None


@dataclass(frozen=True)
class ResumoFatura:
    total: Decimal
    propria: Decimal
    terceiros: Decimal


@dataclass(frozen=True)
class Limite:
    limite: Decimal
    usado: Decimal
    disponivel: Decimal


_SELECT_LINHA = (
    "SELECT linha_id, nome, limite, versao FROM linha_credito "
    "WHERE user_id = %s AND vigente AND NOT excluida"
)


async def listar_linhas(conn: psycopg.AsyncConnection, user_id: int) -> list[Linha]:
    cur = await conn.execute(_SELECT_LINHA + " ORDER BY linha_id", (user_id,))
    return [Linha(*linha) for linha in await cur.fetchall()]


async def obter_linha(conn: psycopg.AsyncConnection, user_id: int, linha_id: int) -> Linha | None:
    cur = await conn.execute(_SELECT_LINHA + " AND linha_id = %s", (user_id, linha_id))
    linha = await cur.fetchone()
    return Linha(*linha) if linha else None


async def gravar_linha(
    conn: psycopg.AsyncConnection,
    user_id: int,
    *,
    nome: str,
    limite: Decimal,
    linha_id: int | None = None,
    versao: int | None = None,
) -> int:
    """Cria (sem `linha_id`) ou edita (com a `versao` lida). Erros de regra: SQLSTATE AB***."""
    cur = await conn.execute(
        "SELECT linha_id FROM linha_credito_gravar(%s, %s, %s, %s, %s)",
        (user_id, linha_id, versao, nome, limite),
    )
    linha = await cur.fetchone()
    if linha is None:
        raise RuntimeError("linha_credito_gravar não devolveu linha")
    return int(linha[0])


async def limite_da_linha(
    conn: psycopg.AsyncConnection, user_id: int, linha_id: int, em: date | None
) -> Limite | None:
    cur = await conn.execute(
        "SELECT limite, usado, disponivel FROM limite_linha(%s, %s, %s)", (user_id, linha_id, em)
    )
    linha = await cur.fetchone()
    return Limite(*linha) if linha else None


async def eh_cartao(conn: psycopg.AsyncConnection, user_id: int, conta_id: int) -> bool:
    cur = await conn.execute(
        "SELECT 1 FROM conta_versao WHERE user_id = %s AND conta_id = %s AND tipo = 'divida' "
        "AND vigente AND NOT excluida",
        (user_id, conta_id),
    )
    return await cur.fetchone() is not None


async def gravar_fechamento(
    conn: psycopg.AsyncConnection, user_id: int, conta_id: int, dia: int, vigente_desde: date
) -> None:
    await conn.execute(
        "SELECT fechamento_gravar(%s, %s, %s, %s)", (user_id, conta_id, dia, vigente_desde)
    )


async def listar_fechamentos(
    conn: psycopg.AsyncConnection, user_id: int, conta_id: int
) -> list[Fechamento]:
    cur = await conn.execute(
        "SELECT dia, vigente_desde FROM fechamento_vigente "
        "WHERE user_id = %s AND conta_id = %s ORDER BY vigente_desde DESC",
        (user_id, conta_id),
    )
    return [Fechamento(*linha) for linha in await cur.fetchall()]


async def itens_da_fatura(
    conn: psycopg.AsyncConnection, user_id: int, conta_id: int, competencia: str
) -> list[ItemFatura]:
    cur = await conn.execute(
        "SELECT transacao_id, versao, parcela, parcelas, data_compra, valor, descricao, pessoa_id "
        "FROM fatura_itens(%s, %s, %s)",
        (user_id, conta_id, competencia),
    )
    return [ItemFatura(*linha) for linha in await cur.fetchall()]


async def fechamento_da_fatura(
    conn: psycopg.AsyncConnection, user_id: int, conta_id: int, competencia: str, hoje: date
) -> tuple[date | None, bool | None]:
    """(data do fechamento efetivo, aberta?). Aberta = `hoje` anterior ao fechamento (ADR 048
    item 9). Sem dia de fechamento cadastrado a função devolve nulo e a situação é desconhecida."""
    cur = await conn.execute(
        "SELECT f, f > %s FROM (SELECT fatura_fechamento(%s, %s, %s) AS f) t",
        (hoje, user_id, conta_id, competencia),
    )
    linha = await cur.fetchone()
    if linha is None or linha[0] is None:
        return None, None
    return linha[0], bool(linha[1])


async def resumo_da_fatura(
    conn: psycopg.AsyncConnection, user_id: int, conta_id: int, competencia: str
) -> ResumoFatura:
    """Total = própria + terceiros (ADR 045 item 7); a soma é feita pelo banco."""
    cur = await conn.execute(
        "SELECT total, propria, terceiros FROM fatura_resumo(%s, %s, %s)",
        (user_id, conta_id, competencia),
    )
    linha = await cur.fetchone()
    if linha is None:
        raise RuntimeError("fatura_resumo não devolveu linha")
    return ResumoFatura(*linha)
