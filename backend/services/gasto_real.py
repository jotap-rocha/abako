"""Gasto real e receita do mês (SPEC-008, ADR 046).

Toda a regra vive nas funções da migração 0009; aqui só se monta a chamada, sempre com o
`user_id` da sessão (INV-13). Nenhum cálculo financeiro em Python. Valores nunca vão a log.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime
from decimal import Decimal
from zoneinfo import ZoneInfo

import psycopg

FUSO = ZoneInfo("America/Sao_Paulo")


def hoje_civil() -> date:
    """Data civil de hoje em America/Sao_Paulo (nunca a data UTC do servidor)."""
    return datetime.now(FUSO).date()


@dataclass(frozen=True)
class GastoPorConta:
    conta_id: int
    valor: Decimal


@dataclass(frozen=True)
class GastoRealMes:
    total: Decimal
    por_conta: list[GastoPorConta]


@dataclass(frozen=True)
class ReceitaMes:
    caixa: Decimal
    beneficio: Decimal
    total: Decimal


async def gasto_real(conn: psycopg.AsyncConnection, user_id: int, mes: str) -> GastoRealMes:
    """Mês inválido: o banco recusa com AB422 (traduzido pelo router)."""
    cur = await conn.execute("SELECT gasto_real(%s, %s)", (user_id, mes))
    linha = await cur.fetchone()
    if linha is None:
        raise RuntimeError("gasto_real não devolveu linha")
    cur = await conn.execute(
        "SELECT conta_id, valor FROM gasto_real_por_conta(%s, %s)", (user_id, mes)
    )
    return GastoRealMes(linha[0], [GastoPorConta(*r) for r in await cur.fetchall()])


async def receita(conn: psycopg.AsyncConnection, user_id: int, mes: str) -> ReceitaMes:
    cur = await conn.execute(
        "SELECT receita_caixa(%s, %s), receita_beneficio(%s, %s), receita_total(%s, %s)",
        (user_id, mes, user_id, mes, user_id, mes),
    )
    linha = await cur.fetchone()
    if linha is None:
        raise RuntimeError("receita não devolveu linha")
    return ReceitaMes(*linha)
