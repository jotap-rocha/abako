"""SPEC-005-AC-5, AC-6 e AC-7 (INV-07, INV-31): fechamento do cartão, dia inexistente e vigência.

Esperados de F-FECH-01, F-FECH-02 e F-FECH-03 (fixtures/numericos.yaml), calculados à mão.
"""

from __future__ import annotations

from datetime import date
from typing import Any

import psycopg
import pytest

from tests.db.util_lancamento import (
    Recusa,
    ano_atras,
    cartao,
    compra,
    fechar,
    linha_credito,
    parcelas_da,
)
from tests.db.util_saldo import fixture, novo_usuario

pytestmark = pytest.mark.banco


def _cartao(conn: psycopg.Connection) -> tuple[int, int]:
    """Usuário e cartão SEM fechamento (cada teste cadastra o seu)."""
    uid = novo_usuario(conn)
    linha, _ = linha_credito(conn, uid, "linha", "5000.00")
    return uid, cartao(conn, uid, "cartao", linha)


def _competencias(
    conn: psycopg.Connection, uid: int, c: int, compras: list[dict[str, Any]]
) -> list[str]:
    saida: list[str] = []
    for item in compras:
        tid, _, _ = compra(conn, uid, c, ano_atras(item["data"]), item["total"], item["parcelas"])
        saida.append(parcelas_da(conn, uid, tid)[0][1])
    return saida


def test_dia_inexistente(conn: psycopg.Connection) -> None:
    f1 = fixture("F-FECH-01")
    obtido = [
        conn.execute(
            "SELECT fechamento_efetivo(%s, %s)",
            (f1["entrada"]["dia_fechamento"], date.fromisoformat(f"{mes}-01")),
        ).fetchone()
        for mes in f1["entrada"]["meses"]
    ]
    assert [r[0] for r in obtido if r] == [
        date.fromisoformat(d) for d in f1["esperado"]["fechamento_efetivo"]
    ]

    # na compra: com fechamento 31, 27/02 fecha em fevereiro e 28/02 (último dia) vai para março
    f2 = fixture("F-FECH-02")
    uid, c = _cartao(conn)
    fechar(conn, uid, c, f2["entrada"]["cartao_dia_31"]["dia_fechamento"], "2000-01-01")
    obtidas = _competencias(conn, uid, c, f2["entrada"]["cartao_dia_31"]["compras"])
    assert obtidas == [ano_atras(x) for x in f2["esperado"]["competencias_dia_31"]]


def test_compra_no_dia_do_fechamento(conn: psycopg.Connection) -> None:
    f = fixture("F-FECH-02")
    uid, c = _cartao(conn)
    fechar(conn, uid, c, f["entrada"]["cartao"]["dia_fechamento"], "2000-01-01")
    obtidas = _competencias(conn, uid, c, f["entrada"]["compras"])
    # antes do dia 10: fatura que fecha; no dia 10 e depois: a seguinte (inclusive virada de ano)
    assert obtidas == [ano_atras(x) for x in f["esperado"]["competencias"]]


def test_vigencia_do_fechamento(conn: psycopg.Connection) -> None:
    f = fixture("F-FECH-03")
    primeira, segunda = f["entrada"]["vigencias"]
    uid, c = _cartao(conn)
    fechar(conn, uid, c, primeira["dia"], ano_atras(primeira["desde"]))
    compras = f["entrada"]["compras"]
    esperado = [ano_atras(x) for x in f["esperado"]["competencias"]]

    # a compra de antes da mudança usa o dia vigente nela e não é recalculada depois
    antes = _competencias(conn, uid, c, compras[:1])
    fechar(conn, uid, c, segunda["dia"], ano_atras(segunda["desde"]))
    depois = _competencias(conn, uid, c, compras[1:])
    assert antes + depois == esperado
    gravadas = conn.execute(
        "SELECT competencia FROM transacao_vigente WHERE user_id = %s ORDER BY data_transacao",
        (uid,),
    ).fetchall()
    assert [r[0] for r in gravadas] == esperado

    # um fechamento retroativo (vale desde 2025-03-01) não mexe nas compras já gravadas, nem
    # quando a compra é editada sem mudar cartão ou data (a competência é gravada)
    fechar(conn, uid, c, 20, ano_atras("2026-03-01"))
    tid = conn.execute(
        "SELECT transacao_id FROM transacao_vigente WHERE user_id = %s AND data_transacao = %s",
        (uid, date.fromisoformat(ano_atras("2026-03-15"))),
    ).fetchone()
    assert tid is not None
    _, v2, _ = compra(
        conn, uid, c, ano_atras("2026-03-15"), "10.00", 1,
        transacao_id=int(tid[0]), versao=1, descricao="editada",
    )  # fmt: skip
    assert v2 == 2
    assert parcelas_da(conn, uid, int(tid[0]))[0][1] == esperado[0]
    # compra nova nessa data já usa o dia 20 (vigente desde 2025-03-01): 15/03 < 20, fatura de março
    novo, _, _ = compra(conn, uid, c, ano_atras("2026-03-15"), "10.00", 1)
    assert parcelas_da(conn, uid, novo)[0][1] == ano_atras("2026-03")


def test_edicao_que_muda_a_data_recalcula_a_competencia(conn: psycopg.Connection) -> None:
    f = fixture("F-FECH-03")
    primeira, segunda = f["entrada"]["vigencias"]
    uid, c = _cartao(conn)
    fechar(conn, uid, c, primeira["dia"], ano_atras(primeira["desde"]))
    fechar(conn, uid, c, segunda["dia"], ano_atras(segunda["desde"]))
    c0, _, c2 = f["entrada"]["compras"]  # 15/03 (dia 10) e 20/04 (dia 20)
    esperado = f["esperado"]["competencias"]  # ["2026-04", "2026-04", "2026-05"]

    tid, v1, _ = compra(conn, uid, c, ano_atras(c0["data"]), "10.00", 2)
    assert [p[1] for p in parcelas_da(conn, uid, tid)] == [
        ano_atras(esperado[0]),
        ano_atras("2026-05"),
    ]
    # mover a compra para 20/04 passa a usar o dia 20 vigente nessa data: fatura de maio, e as
    # duas parcelas seguem em meses consecutivos a partir dela
    _, v2, _ = compra(
        conn, uid, c, ano_atras(c2["data"]), "10.00", 2, transacao_id=tid, versao=v1
    )  # fmt: skip
    assert v2 == v1 + 1
    assert [p[1] for p in parcelas_da(conn, uid, tid)] == [
        ano_atras(esperado[2]),
        ano_atras("2026-06"),
    ]


def test_edicao_que_muda_o_cartao_recalcula_a_competencia(conn: psycopg.Connection) -> None:
    uid, a = _cartao(conn)
    linha, _ = linha_credito(conn, uid, "outra", "5000.00")
    b = cartao(conn, uid, "cartao-b", linha)
    fechar(conn, uid, a, 10, "2000-01-01")
    fechar(conn, uid, b, 20, "2000-01-01")
    # 15/04: no cartão de fechamento 10 já passou (fatura de maio); no de 20 ainda não (abril)
    tid, v1, _ = compra(conn, uid, a, "2025-04-15", "10.00", 1)
    assert parcelas_da(conn, uid, tid)[0][1] == "2025-05"
    compra(conn, uid, b, "2025-04-15", "10.00", 1, transacao_id=tid, versao=v1)
    assert parcelas_da(conn, uid, tid)[0][1] == "2025-04"
    conta_atual = conn.execute(
        "SELECT DISTINCT conta_id FROM transacao_vigente WHERE user_id = %s AND transacao_id = %s",
        (uid, tid),
    ).fetchall()
    assert conta_atual == [(b,)]


def test_fechamento_identico_nao_duplica(conn: psycopg.Connection) -> None:
    uid, c = _cartao(conn)

    def registros() -> int:
        linha = conn.execute(
            "SELECT count(*) FROM cartao_fechamento WHERE user_id = %s AND conta_id = %s",
            (uid, c),
        ).fetchone()
        assert linha is not None
        return int(linha[0])

    def gravar(dia_fech: int, desde: str) -> int:
        linha = conn.execute(
            "SELECT fechamento_gravar(%s, %s, %s, %s)",
            (uid, c, dia_fech, date.fromisoformat(desde)),
        ).fetchone()
        assert linha is not None
        return int(linha[0])

    primeiro = gravar(10, "2025-01-01")
    assert gravar(10, "2025-01-01") == primeiro  # repetição: devolve o existente
    assert registros() == 1
    # outro dia na mesma vigência vira novo registro (vale o último) e outra vigência também
    mudou = gravar(20, "2025-01-01")
    assert mudou != primeiro
    assert registros() == 2
    assert gravar(10, "2025-02-01") not in (primeiro, mudou)
    assert registros() == 3
    # voltar ao dia anterior na mesma vigência não é repetição do vigente: registra de novo
    assert gravar(10, "2025-01-01") not in (primeiro, mudou)
    assert registros() == 4
    dia_vigente = conn.execute(
        "SELECT dia FROM fechamento_vigente WHERE user_id = %s AND conta_id = %s "
        "AND vigente_desde = %s",
        (uid, c, date(2025, 1, 1)),
    ).fetchone()
    assert dia_vigente == (10,)


def test_fechamento_exige_vigencia_e_dia_valido(conn: psycopg.Connection) -> None:
    uid, c = _cartao(conn)
    with Recusa(conn, "AB422"):  # sem fechamento vigente na data da compra
        compra(conn, uid, c, "2025-01-05", "10.00", 1)
    fechar(conn, uid, c, 10, "2025-02-01")
    with Recusa(conn, "AB422"):  # a compra é anterior à primeira vigência
        compra(conn, uid, c, "2025-01-05", "10.00", 1)
    for dia in (0, 32):
        with Recusa(conn, "AB422"):
            fechar(conn, uid, c, dia, "2025-01-01")
    with Recusa(conn, "AB404"):  # só cartão tem fechamento
        fechar(conn, uid, 999_999_999, 10, "2025-01-01")
