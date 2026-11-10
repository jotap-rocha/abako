"""INV-09 / INV-29 / SPEC-004-AC-2: editar cria nova versão; só a vigente conta."""

from __future__ import annotations

from decimal import Decimal

import psycopg
import pytest

from tests.db.util_lancamento import Recusa, apagar_usuario, conta, corrida, lancar, versoes
from tests.db.util_saldo import fixture, novo_usuario, saldo, snapshot

pytestmark = pytest.mark.banco


def test_edicao_cria_versao(conn: psycopg.Connection) -> None:
    # F-SALDO-02: t1 editada de -80 para -60; saldo usa só a vigente.
    f = fixture("F-SALDO-02")
    uid = novo_usuario(conn)
    c = conta(conn, uid, "corrente")
    snapshot(conn, uid, c, f["entrada"]["snapshot"]["data"], f["entrada"]["snapshot"]["valor"])

    tid, v1, _ = lancar(conn, uid, "debito", "2026-02-02", c, "80.00", descricao="mercado")
    _, v2, criou = lancar(
        conn, uid, "debito", "2026-02-02", c, "60.00", transacao_id=tid, versao=v1
    )
    assert (v1, v2, criou) == (1, 2, True)

    historico = versoes(conn, uid, tid)
    assert len(historico) == f["esperado"]["historico_t1"]
    assert [(h.versao, h.vigente, h.valor) for h in historico] == [
        (1, False, Decimal("-80.00")),
        (2, True, Decimal("-60.00")),
    ]
    assert saldo(conn, uid, c, "2026-02-28") == Decimal("440.00")


def test_editar_transferencia_versiona_as_duas_pernas(conn: psycopg.Connection) -> None:
    uid = novo_usuario(conn)
    a = conta(conn, uid, "a")
    b = conta(conn, uid, "b")
    d = conta(conn, uid, "d")
    tid, v1, _ = lancar(conn, uid, "transferencia", "2026-02-05", a, "100.00", destino=b)
    lancar(
        conn,
        uid,
        "transferencia",
        "2026-02-05",
        a,
        "120.00",
        destino=d,
        transacao_id=tid,
        versao=v1,
    )

    vigentes = [(v.perna, v.conta_id, v.valor) for v in versoes(conn, uid, tid) if v.vigente]
    assert vigentes == [(1, a, Decimal("-120.00")), (2, d, Decimal("120.00"))]
    antigas = [v for v in versoes(conn, uid, tid) if not v.vigente]
    assert [(v.versao, v.perna) for v in antigas] == [(1, 1), (1, 2)]

    # Mudar o tipo de transferência para débito some com a perna 2 vigente.
    lancar(conn, uid, "debito", "2026-02-05", a, "120.00", transacao_id=tid, versao=2)
    assert [(v.perna, v.valor) for v in versoes(conn, uid, tid) if v.vigente] == [
        (1, Decimal("-120.00"))
    ]


def test_versao_desatualizada_e_recusada_sem_gravar(conn: psycopg.Connection) -> None:
    uid = novo_usuario(conn)
    c = conta(conn, uid, "corrente")
    tid, v1, _ = lancar(conn, uid, "debito", "2026-02-02", c, "10.00")
    lancar(conn, uid, "debito", "2026-02-02", c, "11.00", transacao_id=tid, versao=v1)

    with Recusa(conn, "AB409"):
        lancar(conn, uid, "debito", "2026-02-02", c, "12.00", transacao_id=tid, versao=v1)
    assert len(versoes(conn, uid, tid)) == 2
    with Recusa(conn, "AB404"):
        lancar(conn, uid, "debito", "2026-02-02", c, "12.00", transacao_id=999_999_999, versao=1)


def test_duas_edicoes_simultaneas_so_uma_passa(esquema: str) -> None:
    """Duas conexões editam a mesma versão: a segunda espera a trava e recebe 409 (ADR 029)."""
    with psycopg.connect(esquema) as prep:
        uid = novo_usuario(prep)
        c = conta(prep, uid, "corrente")
        tid, v1, _ = lancar(prep, uid, "debito", "2026-02-02", c, "10.00")
        prep.commit()
    try:
        _, segunda = corrida(
            esquema,
            lambda a: lancar(
                a, uid, "debito", "2026-02-02", c, "20.00", transacao_id=tid, versao=v1
            ),
            lambda b: lancar(
                b, uid, "debito", "2026-02-02", c, "30.00", transacao_id=tid, versao=v1
            ),
        )
        assert segunda == "AB409"
        with psycopg.connect(esquema) as ver:
            vigentes = [v for v in versoes(ver, uid, tid) if v.vigente]
            assert [(v.versao, v.valor) for v in vigentes] == [(2, Decimal("-20.00"))]
    finally:
        apagar_usuario(esquema, uid)


def test_editar_debito_para_transferencia_e_rendimento(conn: psycopg.Connection) -> None:
    uid = novo_usuario(conn)
    a = conta(conn, uid, "a")
    b = conta(conn, uid, "b")
    tid, v1, _ = lancar(conn, uid, "debito", "2026-02-05", a, "40.00")
    lancar(
        conn, uid, "transferencia", "2026-02-05", a, "40.00", destino=b, transacao_id=tid, versao=v1
    )
    assert [(v.perna, v.conta_id, v.valor) for v in versoes(conn, uid, tid) if v.vigente] == [
        (1, a, Decimal("-40.00")),
        (2, b, Decimal("40.00")),
    ]

    rid, r1, _ = lancar(conn, uid, "rendimento", "2026-02-05", b, bruto="10.00", imposto="1.50")
    lancar(
        conn,
        uid,
        "rendimento",
        "2026-02-05",
        b,
        bruto="12.00",
        imposto="2.00",
        transacao_id=rid,
        versao=r1,
    )
    assert [(v.versao, v.valor) for v in versoes(conn, uid, rid) if v.vigente] == [
        (2, Decimal("10.00"))
    ]
