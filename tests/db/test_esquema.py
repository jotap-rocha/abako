"""SPEC-001-AC-7 (INV-13) e SPEC-001-AC-10 (INV-14): user_id em toda tabela, dinheiro NUMERIC."""

from __future__ import annotations

from decimal import Decimal

import psycopg
import pytest

pytestmark = pytest.mark.banco

# Tabela de infraestrutura do Alembic: não é dado do usuário.
INFRA = {"alembic_version"}
TIPOS_FLUTUANTES = {"real", "double precision", "money"}
NOMES_MONETARIOS = ("valor", "saldo", "limite", "montante", "imposto", "preco")


def _tabelas(conn: psycopg.Connection) -> set[str]:
    linhas = conn.execute(
        "SELECT table_name FROM information_schema.tables "
        "WHERE table_schema = 'public' AND table_type = 'BASE TABLE'"
    ).fetchall()
    return {r[0] for r in linhas} - INFRA


def test_toda_tabela_tem_user_id(conn: psycopg.Connection) -> None:
    tabelas = _tabelas(conn)
    assert {"usuario", "conta_versao", "transacao_versao"} <= tabelas
    com_user_id = {
        r[0]
        for r in conn.execute(
            "SELECT table_name FROM information_schema.columns "
            "WHERE table_schema = 'public' AND column_name = 'user_id'"
        ).fetchall()
    }
    assert tabelas - com_user_id == set()


def test_dinheiro_numeric(conn: psycopg.Connection) -> None:
    colunas = conn.execute(
        "SELECT table_name, column_name, data_type FROM information_schema.columns "
        "WHERE table_schema = 'public'"
    ).fetchall()
    flutuantes = [(t, c) for t, c, tipo in colunas if tipo in TIPOS_FLUTUANTES]
    assert flutuantes == []
    monetarias = [
        (t, c, tipo)
        for t, c, tipo in colunas
        if t not in INFRA and any(n in c for n in NOMES_MONETARIOS)
    ]
    assert ("transacao_versao", "valor", "numeric") in monetarias
    assert [m for m in monetarias if m[2] != "numeric"] == []

    # Centavos exatos: em float, 0.10 + 0.20 daria 0.30000000000000004.
    linha = conn.execute("INSERT INTO usuario (login) VALUES ('u_numeric') RETURNING user_id")
    uid = linha.fetchone()[0]  # type: ignore[index]
    soma = conn.execute(
        "WITH t AS (INSERT INTO transacao_versao (user_id, conta_id, data_transacao, valor) "
        "VALUES (%s, 1, DATE '2026-01-05', 0.10), (%s, 1, DATE '2026-01-05', 0.20) "
        "RETURNING valor) SELECT sum(valor) FROM t",
        (uid, uid),
    ).fetchone()
    assert soma is not None
    assert soma[0] == Decimal("0.30")
