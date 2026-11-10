"""INV-36 / SPEC-004-AC-6: rendimento registra bruto e imposto; a conta recebe o líquido."""

from __future__ import annotations

import psycopg
import pytest

from tests.db.util_lancamento import Recusa, conta, lancar
from tests.db.util_saldo import dec, fixture, novo_usuario, saldo, snapshot

pytestmark = pytest.mark.banco


def test_liquido_creditado(conn: psycopg.Connection) -> None:
    f = fixture("F-REND-01")
    entrada, esperado = f["entrada"], f["esperado"]
    uid = novo_usuario(conn)
    c = conta(conn, uid, "corrente")
    reserva = conta(conn, uid, "caixinha", "reserva", mae=c)
    snapshot(conn, uid, reserva, entrada["snapshot"]["data"], entrada["snapshot"]["valor"])

    r = entrada["rendimento"]
    tid, _, _ = lancar(
        conn, uid, "rendimento", r["data"], reserva, bruto=r["bruto"], imposto=r["imposto"]
    )

    linha = conn.execute(
        "SELECT valor, bruto, imposto, tipo FROM lancamento_vigente "
        "WHERE user_id = %s AND transacao_id = %s",
        (uid, tid),
    ).fetchone()
    assert linha is not None
    assert linha == (dec(esperado["creditado"]), dec(r["bruto"]), dec(r["imposto"]), "rendimento")
    assert saldo(conn, uid, reserva, r["data"]) == dec(esperado["saldo_derivado"])
    # O imposto não sai de nenhuma conta: a corrente não muda.
    assert saldo(conn, uid, c, r["data"]) == dec("0.00")


def test_rendimento_valida_bruto_e_imposto(conn: psycopg.Connection) -> None:
    uid = novo_usuario(conn)
    c = conta(conn, uid, "corrente")
    vale = conta(conn, uid, "vale", "beneficio")

    # Imposto zero (aplicação isenta) é aceito.
    lancar(conn, uid, "rendimento", "2026-03-10", c, bruto="10.00", imposto="0.00")
    casos: list[dict[str, str | None]] = [
        {"bruto": "10.00", "imposto": "10.00"},  # líquido zero
        {"bruto": "10.00", "imposto": "11.00"},
        {"bruto": "0.00", "imposto": "0.00"},
        {"bruto": "10.00", "imposto": None},
        {"bruto": None, "imposto": "1.00"},
    ]
    for caso in casos:
        with Recusa(conn, "AB422"):
            lancar(
                conn,
                uid,
                "rendimento",
                "2026-03-10",
                c,
                bruto=caso["bruto"],
                imposto=caso["imposto"],
            )
    with Recusa(conn, "AB422"):  # o valor sai de bruto − imposto; não se informa
        lancar(conn, uid, "rendimento", "2026-03-10", c, "5.00", bruto="10.00", imposto="1.00")
    with Recusa(conn, "AB422"):  # bruto e imposto são só do rendimento
        lancar(conn, uid, "receita", "2026-03-10", c, "10.00", bruto="10.00", imposto="1.00")
    with Recusa(conn, "AB422"):
        lancar(conn, uid, "rendimento", "2026-03-10", vale, bruto="10.00", imposto="1.00")
