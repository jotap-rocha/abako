"""Horizonte, vencimento do cartão e situação do R2 (SPEC-010, ADR 048).

Disponível, compromissos, sobra, alerta, vencidas e pendências são calculados pelas funções
`r2_situacao` e `r2_itens` (migração 0011); aqui só se monta a chamada, sempre com o `user_id` da
sessão (INV-13) e `hoje` = data civil de America/Sao_Paulo. Nenhum cálculo em Python.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from decimal import Decimal

import psycopg
from psycopg import IsolationLevel


@dataclass(frozen=True)
class Horizonte:
    dias: int
    vigente_desde: date


@dataclass(frozen=True)
class Vencimento:
    dia: int
    vigente_desde: date


@dataclass(frozen=True)
class Situacao:
    horizonte_dias: int
    data_fim: date
    saldos_correntes: Decimal
    receitas_pendentes: Decimal
    disponivel: Decimal
    fixos_pendentes: Decimal
    faturas_proprias: Decimal
    compromissos: Decimal
    sobra: Decimal
    alerta: bool
    vencidas: int
    pendencias_vencimento: int


@dataclass(frozen=True)
class Item:
    grupo: str
    tipo: str | None
    recorrente_id: int | None
    conta_id: int
    competencia: str | None
    data: date
    valor: Decimal
    bruto: Decimal | None
    pago: Decimal | None
    parcial: bool | None


async def gravar_horizonte(
    conn: psycopg.AsyncConnection, user_id: int, dias: int, vigente_desde: date
) -> None:
    """Valores inválidos: o banco recusa com AB422 (traduzido pelo router)."""
    await conn.execute("SELECT r2_parametro_gravar(%s, %s, %s)", (user_id, dias, vigente_desde))


async def listar_horizontes(conn: psycopg.AsyncConnection, user_id: int) -> list[Horizonte]:
    cur = await conn.execute(
        "SELECT dias, vigente_desde FROM r2_parametro_vigente WHERE user_id = %s "
        "ORDER BY vigente_desde",
        (user_id,),
    )
    return [Horizonte(*r) for r in await cur.fetchall()]


async def obter_horizonte(
    conn: psycopg.AsyncConnection, user_id: int, vigente_desde: date
) -> Horizonte | None:
    cur = await conn.execute(
        "SELECT dias, vigente_desde FROM r2_parametro_vigente "
        "WHERE user_id = %s AND vigente_desde = %s",
        (user_id, vigente_desde),
    )
    linha = await cur.fetchone()
    return None if linha is None else Horizonte(*linha)


async def gravar_vencimento(
    conn: psycopg.AsyncConnection, user_id: int, conta_id: int, dia: int, vigente_desde: date
) -> None:
    await conn.execute(
        "SELECT vencimento_gravar(%s, %s, %s, %s)", (user_id, conta_id, dia, vigente_desde)
    )


async def listar_vencimentos(
    conn: psycopg.AsyncConnection, user_id: int, conta_id: int
) -> list[Vencimento]:
    cur = await conn.execute(
        "SELECT dia, vigente_desde FROM vencimento_vigente "
        "WHERE user_id = %s AND conta_id = %s ORDER BY vigente_desde",
        (user_id, conta_id),
    )
    return [Vencimento(*r) for r in await cur.fetchall()]


async def situacao(conn: psycopg.AsyncConnection, user_id: int, hoje: date) -> Situacao:
    cur = await conn.execute("SELECT * FROM r2_situacao(%s, %s)", (user_id, hoje))
    linha = await cur.fetchone()
    if linha is None:
        raise RuntimeError("r2_situacao não devolveu linha")
    return Situacao(*linha)


async def itens(conn: psycopg.AsyncConnection, user_id: int, hoje: date) -> list[Item]:
    cur = await conn.execute(
        "SELECT grupo, tipo, recorrente_id, conta_id, competencia, data, valor, bruto, pago, "
        "parcial FROM r2_itens(%s, %s)",
        (user_id, hoje),
    )
    return [Item(*r) for r in await cur.fetchall()]


async def situacao_com_itens(
    conn: psycopg.AsyncConnection, user_id: int, hoje: date
) -> tuple[Situacao, list[Item]]:
    """Situação e itens do mesmo instante: uma transação REPEATABLE READ somente leitura, para
    os itens nunca divergirem dos totais sob escrita concorrente."""
    await conn.commit()  # fecha a transação aberta pela sessão; o nível só muda fora de uma
    await conn.set_isolation_level(IsolationLevel.REPEATABLE_READ)
    await conn.set_read_only(True)
    try:
        s = await situacao(conn, user_id, hoje)
        lista = await itens(conn, user_id, hoje)
        await conn.commit()
    except BaseException:
        await conn.rollback()
        raise
    finally:
        await conn.set_read_only(None)
        await conn.set_isolation_level(None)
    return s, lista
