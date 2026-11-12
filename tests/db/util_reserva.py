"""Montagem de cenários da reserva (SPEC-009) no `tst` e leitura de `reserva_situacao`."""

from __future__ import annotations

from datetime import date
from decimal import Decimal
from typing import Any

import psycopg

from tests.db.util_lancamento import conta, lancar
from tests.db.util_saldo import dec, dia, snapshot

COLUNAS = (
    "contas_reserva",
    "saldo_liquido",
    "imposto_acumulado",
    "saldo_bruto",
    "meses_meta",
    "gasto_essencial",
    "meta",
    "nivel",
    "falta",
    "cobertura_meses",
    "data_alvo",
    "meses_ate_alvo",
    "alvo_vencida",
    "aporte_mensal",
    "config_pendente",
)


def nova_reserva(
    conn: psycopg.Connection,
    uid: int,
    nome: str,
    snap: dict[str, str] | None = None,
    rendimentos: list[dict[str, str]] | None = None,
    tipo: str = "reserva",
) -> int:
    """Conta (reserva por padrão) com snapshot inicial e rendimentos opcionais."""
    corrente = conta(conn, uid, f"corrente_{nome}")
    c = conta(conn, uid, nome, tipo, mae=corrente)
    if snap is not None:
        snapshot(conn, uid, c, snap["data"], snap["valor"])
    for r in rendimentos or []:
        lancar(conn, uid, "rendimento", r["data"], c, bruto=r["bruto"], imposto=r["imposto"])
    return c


def parametro(
    conn: psycopg.Connection,
    uid: int,
    *,
    desde: str,
    meses: int,
    gasto: str,
    alvo: str | None = None,
) -> int:
    linha = conn.execute(
        "SELECT reserva_parametro_gravar(%s, %s, %s, %s, %s)",
        (uid, meses, dec(gasto), None if alvo is None else dia(alvo), dia(desde)),
    ).fetchone()
    assert linha is not None
    return int(linha[0])


def situacao(conn: psycopg.Connection, uid: int, hoje: str | date) -> dict[str, Any]:
    quando = dia(hoje) if isinstance(hoje, str) else hoje
    linha = conn.execute(
        f"SELECT {', '.join(COLUNAS)} FROM reserva_situacao(%s, %s)",  # noqa: S608
        (uid, quando),
    ).fetchone()
    assert linha is not None
    return dict(zip(COLUNAS, linha, strict=True))


def d(texto: str | None) -> Decimal | None:
    return None if texto is None else dec(texto)
