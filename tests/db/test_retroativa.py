"""SPEC-003-AC-3 (INV-30): edição retroativa não altera o snapshot e o R4 sinaliza."""

from __future__ import annotations

import psycopg
import pytest

from tests.db.util_saldo import (
    dec,
    dia,
    editar,
    fixture,
    nova_conta,
    novo_usuario,
    r4,
    saldo,
    snapshot,
    transacao,
)

pytestmark = pytest.mark.banco


def _snapshots(conn: psycopg.Connection, uid: int) -> list[tuple[int, str, str]]:
    linhas = conn.execute(
        "SELECT id, data_snapshot::text, valor::text FROM snapshot_saldo "
        "WHERE user_id = %s ORDER BY id",
        (uid,),
    ).fetchall()
    return [(r[0], r[1], r[2]) for r in linhas]


def test_edicao_retroativa_sinaliza_r4(conn: psycopg.Connection) -> None:
    f = fixture("F-SALDO-03")
    e = f["entrada"]
    uid = novo_usuario(conn)
    conta = nova_conta(conn, uid)
    snapshot(conn, uid, conta, e["snapshot_1"]["data"], e["snapshot_1"]["valor"])
    t = e["transacao"]
    id_t = transacao(conn, uid, conta, t["data"], t["versoes"][0]["valor"])
    snapshot(conn, uid, conta, e["snapshot_2"]["data"], e["snapshot_2"]["valor"])

    antes = f["esperado"]["antes_da_edicao"]
    assert r4(conn, uid) == antes["r4"] == []
    snapshots_antes = _snapshots(conn, uid)

    # edição retroativa: a transação de 01-11 (anterior ao snapshot de 01-14) muda de -50 para -60
    editar(conn, uid, conta, id_t, t["data"], t["versoes"][1]["valor"])

    depois = f["esperado"]["depois_da_edicao"]
    assert saldo(conn, uid, conta, "2026-01-12") == dec(depois["saldo_derivado_em_2026_01_12"])
    assert saldo(conn, uid, conta, "2026-01-14") == dec(depois["saldo_em_2026_01_14"])
    # o saldo atual segue o último snapshot (INV-03): a edição não o move
    assert saldo(conn, uid, conta, "2026-02-01") == dec(depois["saldo_atual"])

    # o snapshot não foi tocado
    assert _snapshots(conn, uid) == snapshots_antes
    assert dec(_snapshots(conn, uid)[-1][2]) == dec(depois["snapshot_2_valor"])

    # o R4 sinaliza exatamente o snapshot de 01-14, sem corrigir nada
    esperado = depois["r4"]
    assert len(esperado) == 1
    assert r4(conn, uid) == [
        (
            conta,
            dia(esperado[0]["data_snapshot"]),
            dec(esperado[0]["valor_snapshot"]),
            dec(esperado[0]["saldo_derivado"]),
            dec(esperado[0]["divergencia"]),
        )
    ]
    assert depois["corrigida_automaticamente"] is False
    assert _snapshots(conn, uid) == snapshots_antes  # ler o R4 também não escreve nada
