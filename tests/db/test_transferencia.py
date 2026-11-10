"""INV-01 / SPEC-004-AC-1: transferência e investimento têm duas pernas que somam zero."""

from __future__ import annotations

from decimal import Decimal

import psycopg
import pytest

from tests.db.util_lancamento import Recusa, conta, lancar, versoes
from tests.db.util_saldo import dec, fixture, novo_usuario, saldo, snapshot

pytestmark = pytest.mark.banco


def test_duas_pernas_soma_zero(conn: psycopg.Connection) -> None:
    f = fixture("F-TRANSF-01")
    saida, entrada = f["entrada"]
    uid = novo_usuario(conn)
    corrente = conta(conn, uid, "corrente")
    reserva = conta(conn, uid, "reserva", "reserva", mae=corrente)
    snapshot(conn, uid, corrente, "2026-02-01", "1000.00")
    snapshot(conn, uid, reserva, "2026-02-01", "0.00")

    # A API recebe o valor positivo; o banco grava as pernas com sinal.
    tid, versao, criou = lancar(
        conn, uid, "transferencia", "2026-02-05", corrente, entrada["valor"], destino=reserva
    )
    assert (versao, criou) == (1, True)

    pernas = versoes(conn, uid, tid)
    assert [(p.perna, p.conta_id, p.valor) for p in pernas] == [
        (1, corrente, dec(saida["valor"])),
        (2, reserva, dec(entrada["valor"])),
    ]
    assert sum(p.valor for p in pernas) == dec(f["esperado"]["soma_pernas"])
    assert saldo(conn, uid, corrente, "2026-02-05") == Decimal("700.00")
    assert saldo(conn, uid, reserva, "2026-02-05") == Decimal("300.00")


def test_investimento_vai_para_conta_de_investimento(conn: psycopg.Connection) -> None:
    uid = novo_usuario(conn)
    corrente = conta(conn, uid, "corrente")
    reserva = conta(conn, uid, "caixinha", "reserva", mae=corrente)
    invest = conta(conn, uid, "corretora", "investimento")

    tid, _, _ = lancar(conn, uid, "investimento", "2026-02-05", corrente, "50.00", destino=invest)
    assert sum(p.valor for p in versoes(conn, uid, tid)) == Decimal("0.00")

    # Guardar na caixinha (reserva) é transferência, não investimento.
    with Recusa(conn, "AB422"):
        lancar(conn, uid, "investimento", "2026-02-05", corrente, "50.00", destino=reserva)


def test_transferencia_recusa_destino_invalido(conn: psycopg.Connection) -> None:
    uid = novo_usuario(conn)
    outro = novo_usuario(conn)
    corrente = conta(conn, uid, "corrente")
    vale = conta(conn, uid, "vale", "beneficio")
    alheia = conta(conn, outro, "do outro")

    with Recusa(conn, "AB422"):  # mesma conta nas duas pernas
        lancar(conn, uid, "transferencia", "2026-02-05", corrente, "10.00", destino=corrente)
    with Recusa(conn, "AB422"):  # sem destino
        lancar(conn, uid, "transferencia", "2026-02-05", corrente, "10.00")
    with Recusa(conn, "AB422"):  # benefício fica para a SPEC-013
        lancar(conn, uid, "transferencia", "2026-02-05", corrente, "10.00", destino=vale)
    with Recusa(conn, "AB404"):  # conta de outro usuário não existe para este (INV-13)
        lancar(conn, uid, "transferencia", "2026-02-05", corrente, "10.00", destino=alheia)
    with Recusa(conn, "AB422"):  # destino só em transferência
        lancar(conn, uid, "debito", "2026-02-05", corrente, "10.00", destino=vale)


def test_perna_solta_e_barrada_pelo_esquema(conn: psycopg.Connection) -> None:
    """Mesmo o dono não grava perna solta (CHECKs + trigger da 0005, INV-01)."""
    uid = novo_usuario(conn)
    a = conta(conn, uid, "a")
    b = conta(conn, uid, "b")

    def inserir(*pernas: tuple[str, int, int, str]) -> None:
        tid = conn.execute("SELECT nextval('transacao_id_seq')").fetchone()
        assert tid is not None
        # A conferência das pernas roda no commit; aqui ela é antecipada para o fim do comando,
        # e as pernas vão num único INSERT (é assim que ela as vê no commit).
        conn.execute("SET CONSTRAINTS transacao_pernas_ck IMMEDIATE")
        linhas = ", ".join(["(%s, %s, %s, DATE '2026-02-05', %s, %s, %s)"] * len(pernas))
        params: list[object] = []
        for tipo, perna, conta_id, valor in pernas:
            params += [uid, tid[0], conta_id, dec(valor), tipo, perna]
        conn.execute(
            # Só marcadores no texto; os dados vão nos parâmetros.
            "INSERT INTO transacao_versao "
            "(user_id, transacao_id, conta_id, data_transacao, valor, tipo, perna) "
            f"VALUES {linhas}",
            params,
        )

    casos = [
        [("debito", 2, a, "10.00")],  # débito não tem perna 2 (CHECK)
        [("transferencia", 1, a, "10.00")],  # saída com sinal trocado (CHECK)
        [("transferencia", 1, a, "-10.00")],  # transferência com uma perna só (trigger)
        [("transferencia", 1, a, "-10.00"), ("transferencia", 2, b, "9.00")],  # soma ≠ 0
        [("transferencia", 1, a, "-10.00"), ("transferencia", 2, a, "10.00")],  # mesma conta
    ]
    for pernas in casos:
        with pytest.raises(psycopg.errors.CheckViolation), conn.transaction():
            inserir(*pernas)
    # As duas pernas certas passam pela mesma conferência.
    with conn.transaction():
        inserir(("transferencia", 1, a, "-10.00"), ("transferencia", 2, b, "10.00"))
