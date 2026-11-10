"""SPEC-005-AC-2 e AC-4 (INV-07, INV-26): parcela na competência e total da fatura.

Esperados de F-PARC-03 e F-FAT-02 (fixtures/numericos.yaml), calculados à mão.
"""

from __future__ import annotations

from datetime import date

import psycopg
import pytest

from tests.db.util_lancamento import ano_atras, cartao, compra, linha_credito
from tests.db.util_saldo import dec, fixture, novo_usuario

pytestmark = pytest.mark.banco


def _cartao(conn: psycopg.Connection, fechamento: int) -> tuple[int, int]:
    uid = novo_usuario(conn)
    linha, _ = linha_credito(conn, uid, "linha", "5000.00")
    return uid, cartao(conn, uid, "cartao", linha, fechamento, "2000-01-01")


def test_parcela_na_competencia(conn: psycopg.Connection) -> None:
    f = fixture("F-PARC-03")
    uid, c = _cartao(conn, f["entrada"]["cartao"]["dia_fechamento"])
    for i, chave in ((0, "caso_1"), (2, "caso_3")):
        caso = f["entrada"]["casos"][i]
        data = ano_atras(caso["data"])
        tid, _, _ = compra(conn, uid, c, data, caso["total"], caso["parcelas"])
        linhas = conn.execute(
            "SELECT data_transacao, competencia FROM transacao_vigente "
            "WHERE user_id = %s AND transacao_id = %s ORDER BY parcela",
            (uid, tid),
        ).fetchall()
        # cada parcela leva a data da compra e a competência da sua fatura
        assert [str(d) for d, _ in linhas] == [data] * caso["parcelas"], chave
        assert [comp for _, comp in linhas] == [
            ano_atras(x) for x in f["esperado"][chave]["competencias"]
        ], chave
    # a parcela aparece na fatura da própria competência, com o valor positivo da parcela
    itens = conn.execute(
        "SELECT parcela, parcelas, data_compra, valor FROM fatura_itens(%s, %s, %s)",
        (uid, c, ano_atras("2026-12")),
    ).fetchall()
    assert [(p, n, v) for p, n, _, v in itens] == [(1, 3, dec("100.00")), (1, 3, dec("0.03"))]
    assert {d for _, _, d, _ in itens} == {date(2025, 11, 15)}


def test_total_proprio_mais_terceiros(conn: psycopg.Connection) -> None:
    """F-FAT-02: só a fatura própria nesta SPEC (terceiros entram na SPEC-013)."""
    f = fixture("F-FAT-02")
    uid, c = _cartao(conn, f["entrada"]["cartao"]["dia_fechamento"])
    for item in f["entrada"]["compras"]:
        compra(conn, uid, c, ano_atras(item["data"]), item["total"], item["parcelas"])
    for competencia, total in f["esperado"]["faturas"].items():
        linha = conn.execute(
            "SELECT fatura_total(%s, %s, %s)", (uid, c, ano_atras(competencia))
        ).fetchone()
        assert linha == (dec(total),), competencia
    # compras diferentes na mesma competência: a de 2025-04 reúne a 2ª parcela e a compra à vista
    itens = conn.execute(
        "SELECT valor FROM fatura_itens(%s, %s, %s) ORDER BY valor", (uid, c, "2025-04")
    ).fetchall()
    assert [r[0] for r in itens] == [dec("100.00"), dec("200.00")]
    # competência sem parcela: zero, não nulo
    vazia = conn.execute("SELECT fatura_total(%s, %s, '2030-01')", (uid, c)).fetchone()
    assert vazia == (dec("0.00"),)
    # isolamento (INV-13): outro usuário não vê a fatura
    outro = novo_usuario(conn)
    nada = conn.execute(
        "SELECT fatura_total(%s, %s, %s)", (outro, c, ano_atras("2026-04"))
    ).fetchone()
    assert nada == (dec("0.00"),)
