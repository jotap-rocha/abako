"""Reserva, cobertura e aporte (SPEC-009, ADR 047).

Toda a regra (soma das contas, bruto/líquido, nível, cobertura, aporte) vive nas funções da
migração 0010; aqui só se monta a chamada, sempre com o `user_id` da sessão (INV-13). Nenhum
cálculo financeiro em Python. Valores nunca vão a log.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from decimal import Decimal

import psycopg

COLUNAS_SITUACAO = (
    "contas_reserva, saldo_liquido, imposto_acumulado, saldo_bruto, meses_meta, gasto_essencial, "
    "meta, nivel, falta, cobertura_meses, data_alvo, meses_ate_alvo, alvo_vencida, "
    "aporte_mensal, config_pendente"
)


@dataclass(frozen=True)
class Situacao:
    contas_reserva: int
    saldo_liquido: Decimal
    imposto_acumulado: Decimal
    saldo_bruto: Decimal
    meses_meta: int
    gasto_essencial: Decimal | None
    meta: Decimal | None
    nivel: str | None
    falta: Decimal | None
    cobertura_meses: Decimal | None
    data_alvo: date | None
    meses_ate_alvo: int | None
    alvo_vencida: bool
    aporte_mensal: Decimal | None
    config_pendente: bool


@dataclass(frozen=True)
class Parametro:
    vigente_desde: date
    meses: int
    gasto_essencial: Decimal
    data_alvo: date | None


async def situacao(conn: psycopg.AsyncConnection, user_id: int, hoje: date) -> Situacao:
    cur = await conn.execute(
        f"SELECT {COLUNAS_SITUACAO} FROM reserva_situacao(%s, %s)",  # noqa: S608
        (user_id, hoje),
    )
    linha = await cur.fetchone()
    if linha is None:
        raise RuntimeError("reserva_situacao não devolveu linha")
    return Situacao(*linha)


async def gravar_parametro(
    conn: psycopg.AsyncConnection,
    user_id: int,
    meses: int,
    gasto_essencial: Decimal,
    data_alvo: date | None,
    vigente_desde: date,
) -> None:
    """Valores inválidos: o banco recusa com AB422 (traduzido pelo router)."""
    await conn.execute(
        "SELECT reserva_parametro_gravar(%s, %s, %s, %s, %s)",
        (user_id, meses, gasto_essencial, data_alvo, vigente_desde),
    )


async def listar_parametros(conn: psycopg.AsyncConnection, user_id: int) -> list[Parametro]:
    cur = await conn.execute(
        "SELECT vigente_desde, meses, gasto_essencial, data_alvo FROM reserva_parametro_vigente "
        "WHERE user_id = %s ORDER BY vigente_desde",
        (user_id,),
    )
    return [Parametro(*r) for r in await cur.fetchall()]


async def obter_parametro(
    conn: psycopg.AsyncConnection, user_id: int, vigente_desde: date
) -> Parametro | None:
    cur = await conn.execute(
        "SELECT vigente_desde, meses, gasto_essencial, data_alvo FROM reserva_parametro_vigente "
        "WHERE user_id = %s AND vigente_desde = %s",
        (user_id, vigente_desde),
    )
    linha = await cur.fetchone()
    return None if linha is None else Parametro(*linha)
