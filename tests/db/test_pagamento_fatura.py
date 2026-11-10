"""SPEC-005-AC-8 (INV-01, INV-05): pagar a fatura é transferência da corrente para o cartão.

Esperados de F-PAG-01 (fixtures/numericos.yaml), calculados à mão.
"""

from __future__ import annotations

from datetime import date

import psycopg
import pytest

from tests.db.util_lancamento import (
    Recusa,
    ano_atras,
    cartao,
    compra,
    conta,
    lancar,
    linha_credito,
    versoes,
)
from tests.db.util_saldo import dec, fixture, novo_usuario, saldo, snapshot

pytestmark = pytest.mark.banco


def test_pagamento_parcial_abate_a_divida(conn: psycopg.Connection) -> None:
    f = fixture("F-PAG-01")
    e = f["esperado"]
    uid = novo_usuario(conn)
    corrente = conta(conn, uid, "corrente")
    linha, _ = linha_credito(conn, uid, "linha", "5000.00")
    c = cartao(conn, uid, "cartao", linha, 10, "2000-01-01")
    snap = f["entrada"]["corrente"]["snapshot"]
    snapshot(conn, uid, corrente, ano_atras(snap["data"]), snap["valor"])
    ent = f["entrada"]["compra_cartao"]
    compra(conn, uid, c, ano_atras(ent["data"]), ent["total"], ent["parcelas"])

    pg = f["entrada"]["pagamento"]
    data = ano_atras(pg["data"])
    tid, _, _ = lancar(conn, uid, "transferencia", data, corrente, pg["valor"], destino=c)

    # duas pernas, soma zero (INV-01)
    pernas = versoes(conn, uid, tid)
    assert [str(p.valor) for p in pernas] == e["pernas"]
    assert sum(p.valor for p in pernas) == dec(e["soma_pernas"])
    # a dívida diminui e devolve limite; a corrente perde o valor pago
    assert saldo(conn, uid, corrente, data) == dec(e["saldo_corrente"])
    assert saldo(conn, uid, c, data) == dec(e["saldo_cartao"])
    usado = conn.execute(
        "SELECT usado FROM limite_linha(%s, %s, %s)", (uid, linha, date.fromisoformat(data))
    ).fetchone()
    assert usado == (dec(e["limite_usado"]),)
    # Não é gasto real (INV-05): é uma transferência, tipo que o gasto real exclui (INV-04); a
    # compra é o gasto. A view de gasto real é da SPEC-008, então aqui vale o tipo gravado.
    tipo = conn.execute(
        "SELECT tipo FROM lancamento_vigente WHERE user_id = %s AND transacao_id = %s", (uid, tid)
    ).fetchone()
    assert tipo == ("transferencia",)
    assert dec(e["gasto_real_do_pagamento"]) == dec("0.00")  # contrato da fixture


def test_pagamento_maior_que_a_divida_e_regras_do_cartao(conn: psycopg.Connection) -> None:
    uid = novo_usuario(conn)
    corrente = conta(conn, uid, "corrente")
    linha, _ = linha_credito(conn, uid, "linha", "1000.00")
    c = cartao(conn, uid, "cartao", linha, 10, "2000-01-01")
    compra(conn, uid, c, "2025-03-05", "100.00", 1)
    # ADR 043: pagar a mais deixa crédito a favor no cartão; não é erro
    lancar(conn, uid, "transferencia", "2025-03-20", corrente, "150.00", destino=c)
    assert saldo(conn, uid, c, "2025-03-20") == dec("50.00")
    # do cartão não se transfere; investimento não vai para o cartão
    with Recusa(conn, "AB422"):
        lancar(conn, uid, "transferencia", "2025-03-21", c, "10.00", destino=corrente)
    with Recusa(conn, "AB422"):
        lancar(conn, uid, "investimento", "2025-03-21", corrente, "10.00", destino=c)
