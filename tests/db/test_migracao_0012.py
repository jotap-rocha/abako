"""SPEC-011 / ADR 049: a 0012 (alertas) — só uma função; o downgrade a remove, sem recusa."""

from __future__ import annotations

from pathlib import Path

import psycopg
import pytest
from alembic import command
from alembic.config import Config

from tests.db.util_alertas import alertas, reserva_com_saldo

pytestmark = pytest.mark.banco

RAIZ = Path(__file__).resolve().parents[2]


def _funcao_existe(url: str) -> bool:
    with psycopg.connect(url) as conn:
        linha = conn.execute("SELECT count(*) FROM pg_proc WHERE proname = 'alertas'").fetchone()
    assert linha is not None
    return bool(linha[0])


def _revisao(url: str) -> str:
    with psycopg.connect(url) as conn:
        linha = conn.execute("SELECT version_num FROM alembic_version").fetchone()
    assert linha is not None
    return str(linha[0])


def test_downgrade_remove_a_funcao_e_sobe_de_novo(esquema: str) -> None:
    cfg = Config(str(RAIZ / "alembic.ini"))
    assert _revisao(esquema) == "0013"
    assert _funcao_existe(esquema)
    try:
        command.downgrade(cfg, "0011")
        assert _revisao(esquema) == "0011"
        assert not _funcao_existe(esquema)
    finally:
        command.upgrade(cfg, "head")
    assert _revisao(esquema) == "0013"
    assert _funcao_existe(esquema)


def test_nenhuma_tabela_nova_e_leitura_funciona_depois_de_subir(conn: psycopg.Connection) -> None:
    tabelas = conn.execute(
        "SELECT relname FROM pg_class WHERE relkind IN ('r', 'p', 'v') AND relname LIKE '%%alert%%'"
    ).fetchall()
    assert tabelas == []
    uid = reserva_com_saldo(conn, "3000.00")
    assert [a["detalhe"] for a in alertas(conn, uid, "2026-04-01")] == ["reserva_critica"]
