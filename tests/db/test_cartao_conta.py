"""SPEC-005 (ADR 043): regras de `conta_gravar` para o cartão (conta de dívida), direto no banco."""

from __future__ import annotations

import psycopg
import pytest

from tests.db.util_lancamento import Recusa, cartao, compra, conta, lancar, linha_credito
from tests.db.util_saldo import novo_usuario

pytestmark = pytest.mark.banco


def _editar_tipo(
    conn: psycopg.Connection, uid: int, conta_id: int, nome: str, tipo: str, linha: int | None
) -> None:
    conn.execute(
        "SELECT conta_gravar(%s, %s, 1, %s, %s, NULL, %s)", (uid, conta_id, nome, tipo, linha)
    )


def test_tipo_nao_troca_com_lancamentos_de_ou_para_divida(conn: psycopg.Connection) -> None:
    uid = novo_usuario(conn)
    linha, _ = linha_credito(conn, uid, "linha", "1000.00")

    # conta corrente com lançamento não vira cartão
    corrente = conta(conn, uid, "corrente")
    lancar(conn, uid, "receita", "2025-01-05", corrente, "10.00")
    with Recusa(conn, "AB422"):
        _editar_tipo(conn, uid, corrente, "corrente", "divida", linha)

    # cartão com compra não vira outro tipo
    c = cartao(conn, uid, "cartao", linha, 10, "2000-01-01")
    compra(conn, uid, c, "2025-01-05", "30.00", 3)
    with Recusa(conn, "AB422"):
        _editar_tipo(conn, uid, c, "cartao", "corrente", None)

    # cartão só com o pagamento recebido (perna 2 de transferência) também não sai do tipo
    c2 = cartao(conn, uid, "cartao2", linha, 10, "2000-01-01")
    lancar(conn, uid, "transferencia", "2025-01-06", corrente, "5.00", destino=c2)
    with Recusa(conn, "AB422"):
        _editar_tipo(conn, uid, c2, "cartao2", "corrente", None)

    # sem lançamentos a troca é livre: cartão vazio vira corrente (a versão sobe para 2)
    vazio = cartao(conn, uid, "vazio", linha)
    _editar_tipo(conn, uid, vazio, "vazio", "corrente", None)
    tipo = conn.execute(
        "SELECT tipo, versao FROM conta_versao WHERE user_id = %s AND conta_id = %s AND vigente",
        (uid, vazio),
    ).fetchone()
    assert tipo == ("corrente", 2)


def test_linha_de_credito_de_outro_usuario_e_recusada(conn: psycopg.Connection) -> None:
    dono = novo_usuario(conn)
    outro = novo_usuario(conn)
    linha_do_dono, _ = linha_credito(conn, dono, "linha", "1000.00")
    with Recusa(conn, "AB422"):
        conn.execute(
            "SELECT conta_gravar(%s, NULL, NULL, 'intruso', 'divida', NULL, %s)",
            (outro, linha_do_dono),
        )
    # o dono usa a própria linha normalmente
    assert cartao(conn, dono, "cartao", linha_do_dono) > 0
    # cartão sem linha e linha em conta que não é cartão também são recusados
    with Recusa(conn, "AB422"):
        conn.execute("SELECT conta_gravar(%s, NULL, NULL, 'sem', 'divida', NULL, NULL)", (dono,))
    with Recusa(conn, "AB422"):
        conn.execute(
            "SELECT conta_gravar(%s, NULL, NULL, 'x', 'corrente', NULL, %s)",
            (dono, linha_do_dono),
        )
