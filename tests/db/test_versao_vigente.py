"""SPEC-001-AC-8 (INV-27): no máximo uma versão vigente por entidade lógica."""

from __future__ import annotations

import psycopg
import pytest

pytestmark = pytest.mark.banco


def _usuario(conn: psycopg.Connection, login: str) -> int:
    row = conn.execute("INSERT INTO usuario (login) VALUES (%s) RETURNING user_id", (login,))
    return int(row.fetchone()[0])  # type: ignore[index]


def test_segunda_vigente_falha(conn: psycopg.Connection) -> None:
    uid = _usuario(conn, "u_vigente")
    conn.execute(
        "INSERT INTO conta_versao (user_id, conta_id, versao, vigente, nome) "
        "VALUES (%s, 900, 1, true, 'conta teste')",
        (uid,),
    )
    with pytest.raises(psycopg.errors.UniqueViolation):
        conn.execute(
            "INSERT INTO conta_versao (user_id, conta_id, versao, vigente, nome) "
            "VALUES (%s, 900, 2, true, 'conta teste v2')",
            (uid,),
        )


def test_versoes_antigas_convivem_com_uma_vigente(conn: psycopg.Connection) -> None:
    uid = _usuario(conn, "u_historico")
    for versao, vigente in ((1, False), (2, False), (3, True)):
        conn.execute(
            "INSERT INTO transacao_versao (user_id, transacao_id, versao, vigente, conta_id, "
            "data_transacao, valor) VALUES (%s, 901, %s, %s, 1, DATE '2026-01-05', 10.00)",
            (uid, versao, vigente),
        )
    linha = conn.execute(
        "SELECT count(*) FROM transacao_versao WHERE user_id = %s AND vigente", (uid,)
    ).fetchone()
    assert linha == (1,)


def test_mesma_entidade_em_outro_usuario_tem_sua_vigente(conn: psycopg.Connection) -> None:
    a, b = _usuario(conn, "u_a"), _usuario(conn, "u_b")
    for uid in (a, b):
        conn.execute(
            "INSERT INTO conta_versao (user_id, conta_id, versao, nome) VALUES (%s, 902, 1, 'c')",
            (uid,),
        )
