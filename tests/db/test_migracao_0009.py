"""SPEC-008 / ADR 046: a 0009 (gasto real e receita de caixa) — só funções, reversível."""

from __future__ import annotations

from pathlib import Path

import psycopg
import pytest
from alembic import command
from alembic.config import Config

from tests.db.util_lancamento import apagar_usuario, conta, lancar
from tests.db.util_saldo import dec, novo_usuario

pytestmark = pytest.mark.banco

RAIZ = Path(__file__).resolve().parents[2]
FUNCOES = (
    "mes_inicio",
    "gasto_real_itens",
    "gasto_real",
    "gasto_real_por_conta",
    "receita_caixa",
    "receita_beneficio",
    "receita_total",
)


def _existentes(url: str) -> list[str]:
    with psycopg.connect(url) as conn:
        linhas = conn.execute(
            "SELECT proname FROM pg_proc WHERE proname = ANY(%s) ORDER BY proname", (list(FUNCOES),)
        ).fetchall()
    return [r[0] for r in linhas]


def _revisao(url: str) -> str:
    with psycopg.connect(url) as conn:
        linha = conn.execute("SELECT version_num FROM alembic_version").fetchone()
    assert linha is not None
    return str(linha[0])


def test_downgrade_com_dados_remove_so_as_funcoes_e_sobe_de_novo(esquema: str) -> None:
    """A 0009 não cria tabela nem coluna: o downgrade é seguro com dados e não perde nada."""
    cfg = Config(str(RAIZ / "alembic.ini"))
    with psycopg.connect(esquema) as prep:
        uid = novo_usuario(prep)
        corrente = conta(prep, uid, "corrente")
        lancar(prep, uid, "debito", "2025-04-08", corrente, "12.34")
        prep.commit()
    try:
        assert _existentes(esquema) == sorted(FUNCOES)
        command.downgrade(cfg, "0008")
        assert _revisao(esquema) == "0008"
        assert _existentes(esquema) == []
        with psycopg.connect(esquema) as ver:  # o lançamento continua lá
            linha = ver.execute(
                "SELECT count(*) FROM transacao_versao WHERE user_id = %s", (uid,)
            ).fetchone()
            assert linha == (1,)
    finally:
        command.upgrade(cfg, "head")
        apagar_usuario(esquema, uid)
    assert _revisao(esquema) == "0014"
    assert _existentes(esquema) == sorted(FUNCOES)


def test_leituras_funcionam_depois_de_subir_de_novo(conn: psycopg.Connection) -> None:
    uid = novo_usuario(conn)
    corrente = conta(conn, uid, "corrente")
    lancar(conn, uid, "debito", "2025-04-08", corrente, "12.34")
    linha = conn.execute("SELECT gasto_real(%s, '2025-04')", (uid,)).fetchone()
    assert linha == (dec("12.34"),)
