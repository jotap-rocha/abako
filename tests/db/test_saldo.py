"""SPEC-003-AC-1 e AC-4 (INV-03): saldo derivado = último snapshot + transações vigentes."""

from __future__ import annotations

from decimal import Decimal

import psycopg
import pytest

from tests.db.util_saldo import (
    dec,
    fixture,
    nova_conta,
    novo_usuario,
    saldo,
    snapshot,
    transacao,
)

pytestmark = pytest.mark.banco


def test_saldo_derivado_f_saldo_01(conn: psycopg.Connection) -> None:
    f = fixture("F-SALDO-01")
    uid = novo_usuario(conn)
    conta = nova_conta(conn, uid)
    entrada = f["entrada"]
    snapshot(conn, uid, conta, entrada["snapshot"]["data"], entrada["snapshot"]["valor"])
    for t in entrada["transacoes_posteriores"]:
        transacao(conn, uid, conta, t["data"], t["valor"])

    esperado = dec(f["esperado"]["saldo_derivado_em_2026_01_14"])
    assert saldo(conn, uid, conta, entrada["novo_snapshot"]["data"]) == esperado
    # o snapshot novo (1040.00) não muda o derivado: a conferência só sinaliza (R4)
    snapshot(conn, uid, conta, entrada["novo_snapshot"]["data"], entrada["novo_snapshot"]["valor"])
    # com o snapshot de 01-14 como âncora, o saldo daquele dia é o próprio snapshot
    assert saldo(conn, uid, conta, "2026-01-14") == dec(entrada["novo_snapshot"]["valor"])


def test_saldo_versao_vigente_e_exclusao_f_saldo_02(conn: psycopg.Connection) -> None:
    f = fixture("F-SALDO-02")
    uid = novo_usuario(conn)
    conta = nova_conta(conn, uid)
    snap = f["entrada"]["snapshot"]
    snapshot(conn, uid, conta, snap["data"], snap["valor"])

    t1, t2 = f["entrada"]["transacoes"]
    versoes = t1["versoes"]
    id_t1 = transacao(conn, uid, conta, "2026-02-02", versoes[0]["valor"], vigente=False)
    transacao(conn, uid, conta, "2026-02-02", versoes[1]["valor"], transacao_id=id_t1, versao=2)
    transacao(conn, uid, conta, "2026-02-03", t2["versoes"][0]["valor"], excluida=t2["excluida"])

    assert saldo(conn, uid, conta, "2026-02-28") == dec(f["esperado"]["saldo_derivado"])
    historico = conn.execute(
        "SELECT count(*) FROM transacao_versao WHERE user_id = %s AND transacao_id = %s",
        (uid, id_t1),
    ).fetchone()
    assert historico is not None and historico[0] == f["esperado"]["historico_t1"]


def test_saldo_em_data_passada(conn: psycopg.Connection) -> None:
    """AC-4: o saldo de um dia passado usa o snapshot daquela época, não o mais recente."""
    f = fixture("F-SALDO-03")
    uid = novo_usuario(conn)
    conta = nova_conta(conn, uid)
    e = f["entrada"]
    snapshot(conn, uid, conta, e["snapshot_1"]["data"], e["snapshot_1"]["valor"])
    transacao(conn, uid, conta, e["transacao"]["data"], e["transacao"]["versoes"][0]["valor"])
    snapshot(conn, uid, conta, e["snapshot_2"]["data"], e["snapshot_2"]["valor"])

    antes = f["esperado"]["antes_da_edicao"]
    assert saldo(conn, uid, conta, "2026-01-12") == dec(antes["saldo_derivado_em_2026_01_12"])
    assert saldo(conn, uid, conta, "2026-01-14") == dec(antes["saldo_derivado_em_2026_01_14"])
    # antes de qualquer snapshot nada ancora o saldo: parte de zero, só transações
    assert saldo(conn, uid, conta, "2026-01-09") == Decimal("0.00")


def test_snapshot_vale_para_o_fim_do_dia(conn: psycopg.Connection) -> None:
    """Transação do próprio dia do snapshot já está nele; só as posteriores somam (ADR 041)."""
    uid = novo_usuario(conn)
    conta = nova_conta(conn, uid)
    snapshot(conn, uid, conta, "2026-03-10", "100.00")
    transacao(conn, uid, conta, "2026-03-10", "-30.00")  # já refletida no snapshot
    assert saldo(conn, uid, conta, "2026-03-10") == dec("100.00")
    assert saldo(conn, uid, conta, "2026-03-11") == dec("100.00")
    transacao(conn, uid, conta, "2026-03-11", "-5.00")
    assert saldo(conn, uid, conta, "2026-03-11") == dec("95.00")
    # transação além da data consultada não entra
    transacao(conn, uid, conta, "2026-03-20", "-1.00")
    assert saldo(conn, uid, conta, "2026-03-11") == dec("95.00")
    assert saldo(conn, uid, conta, "2026-03-20") == dec("94.00")


def test_sem_snapshot_parte_de_zero(conn: psycopg.Connection) -> None:
    uid = novo_usuario(conn)
    conta = nova_conta(conn, uid)
    assert saldo(conn, uid, conta, "2026-03-10") == dec("0.00")
    transacao(conn, uid, conta, "2026-03-01", "200.00")
    transacao(conn, uid, conta, "2026-03-02", "-50.50")
    assert saldo(conn, uid, conta, "2026-03-10") == dec("149.50")


def test_dois_snapshots_no_mesmo_dia_vale_o_ultimo_registrado(conn: psycopg.Connection) -> None:
    uid = novo_usuario(conn)
    conta = nova_conta(conn, uid)
    snapshot(conn, uid, conta, "2026-03-10", "100.00")  # digitado errado
    snapshot(conn, uid, conta, "2026-03-10", "110.00")  # correção, registrada depois
    assert saldo(conn, uid, conta, "2026-03-10") == dec("110.00")
    guardados = conn.execute(
        "SELECT count(*) FROM snapshot_saldo WHERE user_id = %s", (uid,)
    ).fetchone()
    assert guardados is not None and guardados[0] == 2  # o erro continua como auditoria


def test_saldo_nao_mistura_contas_nem_usuarios(conn: psycopg.Connection) -> None:
    a, b = novo_usuario(conn), novo_usuario(conn)
    conta_a1, conta_a2 = nova_conta(conn, a, "a1"), nova_conta(conn, a, "a2")
    conta_b = nova_conta(conn, b)
    snapshot(conn, a, conta_a1, "2026-03-01", "10.00")
    transacao(conn, a, conta_a1, "2026-03-02", "5.00")
    transacao(conn, a, conta_a2, "2026-03-02", "700.00")
    transacao(conn, b, conta_b, "2026-03-02", "9000.00")
    assert saldo(conn, a, conta_a1, "2026-03-31") == dec("15.00")
    assert saldo(conn, a, conta_a2, "2026-03-31") == dec("700.00")
    # o `user_id` da chamada manda: a conta do outro usuário não aparece para `a`
    assert saldo(conn, a, conta_b, "2026-03-31") == dec("0.00")


def test_transacao_anterior_ao_primeiro_snapshot_nao_conta(conn: psycopg.Connection) -> None:
    """O primeiro snapshot é o saldo inicial: o que veio antes dele já está dentro dele."""
    uid = novo_usuario(conn)
    conta = nova_conta(conn, uid)
    transacao(conn, uid, conta, "2026-01-05", "-999.00")
    snapshot(conn, uid, conta, "2026-01-10", "1000.00")
    assert saldo(conn, uid, conta, "2026-01-31") == dec("1000.00")
    assert saldo(conn, uid, conta, "2026-01-09") == dec("-999.00")  # antes dele: sem âncora


def test_snapshot_retroativo_vira_a_nova_ancora_dos_dias_anteriores(
    conn: psycopg.Connection,
) -> None:
    uid = novo_usuario(conn)
    conta = nova_conta(conn, uid)
    snapshot(conn, uid, conta, "2026-02-10", "500.00")
    transacao(conn, uid, conta, "2026-02-05", "-20.00")
    assert saldo(conn, uid, conta, "2026-02-09") == dec("-20.00")  # ainda sem âncora
    snapshot(conn, uid, conta, "2026-02-01", "300.00")  # informado depois, data anterior
    assert saldo(conn, uid, conta, "2026-02-09") == dec("280.00")
    assert saldo(conn, uid, conta, "2026-02-10") == dec("500.00")
