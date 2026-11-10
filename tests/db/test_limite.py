"""SPEC-005-AC-3 (INV-06): limite usado = dívida total (com parcelas futuras) e pagamento parcial.

Esperados de F-LIM-02 (fixtures/numericos.yaml), calculados à mão.
"""

from __future__ import annotations

from datetime import date

import psycopg
import pytest

from tests.db.util_lancamento import ano_atras, cartao, compra, conta, lancar, linha_credito
from tests.db.util_saldo import dec, fixture, novo_usuario, saldo

pytestmark = pytest.mark.banco


def _limite(conn: psycopg.Connection, uid: int, linha: int, em: str) -> tuple[object, ...]:
    r = conn.execute(
        "SELECT limite, usado, disponivel FROM limite_linha(%s, %s, %s)",
        (uid, linha, date.fromisoformat(em)),
    ).fetchone()
    assert r is not None
    return r


def test_limite_usado(conn: psycopg.Connection) -> None:
    f = fixture("F-LIM-02")
    e = f["esperado"]
    uid = novo_usuario(conn)
    linha, _ = linha_credito(conn, uid, "linha", f["entrada"]["linha"]["limite"])
    x = cartao(conn, uid, "x", linha, 10, "2000-01-01")
    y = cartao(conn, uid, "y", linha, 10, "2000-01-01")
    corrente = conta(conn, uid, "corrente")
    cartoes = {"X": x, "Y": y}
    data = ano_atras("2026-03-05")
    for c in f["entrada"]["compras"]:
        compra(conn, uid, cartoes[c["cartao"]], data, c["total"], c["parcelas"])

    # antes do pagamento: o limite usa o valor total das compras, com as parcelas futuras
    limite = f["entrada"]["linha"]["limite"]
    antes = e["antes_do_pagamento"]
    assert _limite(conn, uid, linha, data) == (
        dec(limite),
        dec(antes["limite_usado"]),
        dec(antes["limite_disponivel"]),
    )

    # pagamento parcial (transferência da corrente para o cartão) devolve limite
    pag = f["entrada"]["pagamentos"][0]
    lancar(
        conn, uid, "transferencia", ano_atras("2026-03-20"), corrente, pag["valor"],
        destino=cartoes[pag["cartao"]],
    )  # fmt: skip
    depois = e["depois_do_pagamento"]
    assert _limite(conn, uid, linha, ano_atras("2026-03-20")) == (
        dec(limite),
        dec(depois["limite_usado"]),
        dec(depois["limite_disponivel"]),
    )
    assert saldo(conn, uid, x, ano_atras("2026-03-20")) == dec(e["saldo_cartao_x"])
    assert saldo(conn, uid, y, ano_atras("2026-03-20")) == dec(e["saldo_cartao_y"])

    # linha pequena: o disponível fica negativo e a compra não é bloqueada
    pequena = f["entrada"]["linha_pequena"]
    linha2, _ = linha_credito(conn, uid, "pequena", pequena["limite"])
    z = cartao(conn, uid, "z", linha2, 10, "2000-01-01")
    for c in pequena["compras"]:
        compra(conn, uid, z, data, c["total"], c["parcelas"])
    esperado = e["linha_pequena"]
    assert _limite(conn, uid, linha2, data) == (
        dec(pequena["limite"]),
        dec(esperado["limite_usado"]),
        dec(esperado["limite_disponivel"]),
    )
    # a primeira linha não foi afetada, e outro usuário não enxerga a linha (INV-13)
    assert _limite(conn, uid, linha, ano_atras("2026-03-20"))[1] == dec(depois["limite_usado"])
    outro = novo_usuario(conn)
    nada = conn.execute(
        "SELECT count(*) FROM limite_linha(%s, %s, %s)", (outro, linha, date(2025, 3, 20))
    ).fetchone()
    assert nada == (0,)
