"""SPEC-003-AC-2 (INV-23): o R4 lista exatamente as contas em que derivado ≠ snapshot."""

from __future__ import annotations

import psycopg
import pytest

from tests.db.util_saldo import (
    dec,
    dia,
    fixture,
    nova_conta,
    novo_usuario,
    r4,
    snapshot,
    transacao,
)

pytestmark = pytest.mark.banco


def test_r4_lista_divergencias(conn: psycopg.Connection) -> None:
    f = fixture("F-SALDO-01")
    e = f["entrada"]
    uid = novo_usuario(conn)
    divergente = nova_conta(conn, uid, "divergente")
    conferida = nova_conta(conn, uid, "conferida")

    snapshot(conn, uid, divergente, e["snapshot"]["data"], e["snapshot"]["valor"])
    for t in e["transacoes_posteriores"]:
        transacao(conn, uid, divergente, t["data"], t["valor"])
    snapshot(conn, uid, divergente, e["novo_snapshot"]["data"], e["novo_snapshot"]["valor"])

    # outra conta, toda conferida: snapshot 500, saída de 100, snapshot 400
    snapshot(conn, uid, conferida, "2026-01-10", "500.00")
    transacao(conn, uid, conferida, "2026-01-12", "-100.00")
    snapshot(conn, uid, conferida, "2026-01-14", "400.00")

    linhas = r4(conn, uid)
    assert len(linhas) == 1  # exatamente a conta que diverge
    conta_id, data, valor_snapshot, derivado, divergencia = linhas[0]
    assert conta_id == divergente
    assert data == dia(e["novo_snapshot"]["data"])
    assert valor_snapshot == dec(e["novo_snapshot"]["valor"])
    assert derivado == dec(f["esperado"]["saldo_derivado_em_2026_01_14"])
    assert divergencia == dec(f["esperado"]["divergencia"])  # derivado - snapshot = +10.00
    assert f["esperado"]["sinalizada_em_r4"] is True


def test_primeiro_snapshot_e_ancora_e_nunca_diverge(conn: psycopg.Connection) -> None:
    uid = novo_usuario(conn)
    conta = nova_conta(conn, uid)
    transacao(conn, uid, conta, "2026-01-05", "-999.00")  # anterior ao saldo inicial
    snapshot(conn, uid, conta, "2026-01-10", "1000.00")
    assert r4(conn, uid) == []


def test_r4_so_olha_o_snapshot_anterior_e_nao_acumula(conn: psycopg.Connection) -> None:
    """Divergência em S2 não contamina S3: cada snapshot é comparado ao anterior."""
    uid = novo_usuario(conn)
    conta = nova_conta(conn, uid)
    snapshot(conn, uid, conta, "2026-01-10", "100.00")
    transacao(conn, uid, conta, "2026-01-11", "-10.00")
    snapshot(conn, uid, conta, "2026-01-12", "80.00")  # derivado 90 -> diverge (+10)
    transacao(conn, uid, conta, "2026-01-13", "-5.00")
    snapshot(conn, uid, conta, "2026-01-14", "75.00")  # 80 - 5 = 75 -> confere

    linhas = r4(conn, uid)
    assert [(linha[1], linha[4]) for linha in linhas] == [(dia("2026-01-12"), dec("10.00"))]


def test_r4_ignora_transacao_excluida_e_versao_antiga(conn: psycopg.Connection) -> None:
    uid = novo_usuario(conn)
    conta = nova_conta(conn, uid)
    snapshot(conn, uid, conta, "2026-01-10", "100.00")
    transacao(conn, uid, conta, "2026-01-11", "-20.00", excluida=True)  # não conta
    snapshot(conn, uid, conta, "2026-01-12", "100.00")
    assert r4(conn, uid) == []


def test_r4_e_isolado_por_usuario(conn: psycopg.Connection) -> None:
    a, b = novo_usuario(conn), novo_usuario(conn)
    conta_b = nova_conta(conn, b)
    snapshot(conn, b, conta_b, "2026-01-10", "100.00")
    snapshot(conn, b, conta_b, "2026-01-12", "1.00")  # diverge, mas é do usuário b
    assert r4(conn, a) == []
    assert len(r4(conn, b)) == 1


def test_r4_usa_so_o_snapshot_vigente_do_dia(conn: psycopg.Connection) -> None:
    """Snapshot digitado errado e corrigido no mesmo dia: só o corrigido é comparado."""
    uid = novo_usuario(conn)
    conta = nova_conta(conn, uid)
    snapshot(conn, uid, conta, "2026-01-10", "100.00")
    transacao(conn, uid, conta, "2026-01-11", "-10.00")
    snapshot(conn, uid, conta, "2026-01-12", "70.00")  # erro de digitação: divergiria (+20)
    assert len(r4(conn, uid)) == 1
    snapshot(conn, uid, conta, "2026-01-12", "90.00")  # correção, registrada depois
    assert r4(conn, uid) == []


def test_r4_com_snapshot_retroativo_recalcula_o_vizinho(conn: psycopg.Connection) -> None:
    uid = novo_usuario(conn)
    conta = nova_conta(conn, uid)
    snapshot(conn, uid, conta, "2026-01-10", "100.00")
    snapshot(conn, uid, conta, "2026-01-20", "100.00")  # confere: nenhuma transação
    assert r4(conn, uid) == []
    transacao(conn, uid, conta, "2026-01-12", "-30.00")
    snapshot(conn, uid, conta, "2026-01-15", "70.00")  # entra no meio, confere com a saída
    # 01-20 agora é comparado ao de 01-15 (70), não ao de 01-10: derivado 70 vs 100
    assert [(x[1], x[4]) for x in r4(conn, uid)] == [(dia("2026-01-20"), dec("-30.00"))]
