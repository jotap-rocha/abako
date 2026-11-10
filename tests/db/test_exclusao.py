"""INV-09 / SPEC-004-AC-5: exclusão é lógica; a transação deixa de contar e o histórico fica."""

from __future__ import annotations

from decimal import Decimal

import psycopg
import pytest

from tests.db.util_lancamento import Recusa, conta, excluir, lancar, versoes
from tests.db.util_saldo import novo_usuario, saldo, snapshot

pytestmark = pytest.mark.banco


def test_exclusao_logica(conn: psycopg.Connection) -> None:
    uid = novo_usuario(conn)
    c = conta(conn, uid, "corrente")
    snapshot(conn, uid, c, "2026-02-01", "500.00")
    tid, v1, _ = lancar(conn, uid, "debito", "2026-02-03", c, "20.00")
    assert saldo(conn, uid, c, "2026-02-28") == Decimal("480.00")

    assert excluir(conn, uid, tid, v1) == 2
    assert saldo(conn, uid, c, "2026-02-28") == Decimal("500.00")
    # Nada foi apagado: a versão 1 continua, e a 2 (vigente) está marcada como excluída.
    assert [(v.versao, v.vigente, v.excluida, v.valor) for v in versoes(conn, uid, tid)] == [
        (1, False, False, Decimal("-20.00")),
        (2, True, True, Decimal("-20.00")),
    ]
    linha = conn.execute(
        "SELECT count(*) FROM lancamento_vigente WHERE user_id = %s AND transacao_id = %s",
        (uid, tid),
    ).fetchone()
    assert linha is not None and linha[0] == 0


def test_excluido_nao_volta_nem_e_editado(conn: psycopg.Connection) -> None:
    uid = novo_usuario(conn)
    c = conta(conn, uid, "corrente")
    tid, v1, _ = lancar(conn, uid, "debito", "2026-02-03", c, "20.00")
    excluir(conn, uid, tid, v1)

    with Recusa(conn, "AB404"):
        lancar(conn, uid, "debito", "2026-02-03", c, "25.00", transacao_id=tid, versao=2)
    with Recusa(conn, "AB404"):
        excluir(conn, uid, tid, 2)
    assert len(versoes(conn, uid, tid)) == 2


def test_excluir_com_versao_antiga_e_conflito(conn: psycopg.Connection) -> None:
    uid = novo_usuario(conn)
    a = conta(conn, uid, "a")
    b = conta(conn, uid, "b")
    tid, v1, _ = lancar(conn, uid, "transferencia", "2026-02-03", a, "20.00", destino=b)
    lancar(
        conn, uid, "transferencia", "2026-02-03", a, "30.00", destino=b, transacao_id=tid, versao=v1
    )

    with Recusa(conn, "AB409"):
        excluir(conn, uid, tid, v1)
    # Excluir a transferência exclui as duas pernas juntas.
    excluir(conn, uid, tid, 2)
    vigentes = [v for v in versoes(conn, uid, tid) if v.vigente]
    assert [(v.perna, v.excluida) for v in vigentes] == [(1, True), (2, True)]
