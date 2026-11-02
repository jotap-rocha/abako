"""SPEC-001-AC-11: campo de versão existe e a chave de idempotência é única por usuário."""

from __future__ import annotations

import psycopg
import pytest

pytestmark = pytest.mark.banco

INSERT = (
    "INSERT INTO transacao_versao (user_id, conta_id, data_transacao, valor, chave_idempotencia) "
    "VALUES (%s, 1, DATE '2026-01-05', 10.00, %s)"
)


def _usuario(conn: psycopg.Connection, login: str) -> int:
    row = conn.execute("INSERT INTO usuario (login) VALUES (%s) RETURNING user_id", (login,))
    return int(row.fetchone()[0])  # type: ignore[index]


def test_campo_de_versao_existe(conn: psycopg.Connection) -> None:
    for tabela in ("conta_versao", "transacao_versao"):
        row = conn.execute(
            "SELECT data_type, is_nullable FROM information_schema.columns "
            "WHERE table_schema = 'public' AND table_name = %s AND column_name = 'versao'",
            (tabela,),
        ).fetchone()
        assert row == ("integer", "NO")


def test_chave_unica_por_usuario(conn: psycopg.Connection) -> None:
    a, b = _usuario(conn, "u_idem_a"), _usuario(conn, "u_idem_b")
    conn.execute(INSERT, (a, "chave-1"))
    conn.execute(INSERT, (b, "chave-1"))  # mesma chave em outro usuário é permitida
    conn.execute(INSERT, (a, None))  # versões seguintes sem chave não colidem
    conn.execute(INSERT, (a, None))
    with pytest.raises(psycopg.errors.UniqueViolation):
        conn.execute(INSERT, (a, "chave-1"))
