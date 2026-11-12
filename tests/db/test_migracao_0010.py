"""SPEC-009 / ADR 047: a 0010 (reserva) — downgrade recusa com parâmetros, sem dados reverte."""

from __future__ import annotations

from pathlib import Path

import psycopg
import pytest
from alembic import command
from alembic.config import Config

from tests.db.util_lancamento import apagar_usuario
from tests.db.util_reserva import nova_reserva, parametro, situacao
from tests.db.util_saldo import dec, novo_usuario

pytestmark = pytest.mark.banco

RAIZ = Path(__file__).resolve().parents[2]
FUNCOES = (
    "reserva_nivel",
    "reserva_cobertura",
    "reserva_aporte",
    "reserva_meses_ate",
    "reserva_situacao",
    "reserva_parametro_gravar",
)


def _existentes(url: str) -> tuple[list[str], list[str]]:
    with psycopg.connect(url) as conn:
        funcoes = conn.execute(
            "SELECT proname FROM pg_proc WHERE proname = ANY(%s) ORDER BY proname", (list(FUNCOES),)
        ).fetchall()
        tabelas = conn.execute(
            "SELECT relname FROM pg_class WHERE relname IN "
            "('reserva_parametro', 'reserva_parametro_vigente') ORDER BY relname"
        ).fetchall()
    return [r[0] for r in funcoes], [r[0] for r in tabelas]


def _revisao(url: str) -> str:
    with psycopg.connect(url) as conn:
        linha = conn.execute("SELECT version_num FROM alembic_version").fetchone()
    assert linha is not None
    return str(linha[0])


def test_downgrade_com_parametros_e_recusado(esquema: str) -> None:
    cfg = Config(str(RAIZ / "alembic.ini"))
    with psycopg.connect(esquema) as prep:
        uid = novo_usuario(prep)
        parametro(prep, uid, desde="2026-01-01", meses=3, gasto="1000.00")
        prep.commit()
    try:
        with pytest.raises(Exception, match="0010"):
            command.downgrade(cfg, "0009")
        assert _revisao(esquema) == "0011"  # a recusa desfaz tudo: nada foi removido
        funcoes, tabelas = _existentes(esquema)
        assert funcoes == sorted(FUNCOES)
        assert tabelas == ["reserva_parametro", "reserva_parametro_vigente"]
        with psycopg.connect(esquema) as ver:  # o parâmetro continua lá
            linha = ver.execute(
                "SELECT count(*) FROM reserva_parametro WHERE user_id = %s", (uid,)
            ).fetchone()
            assert linha == (1,)
    finally:
        with psycopg.connect(esquema) as limpa:
            limpa.execute("DELETE FROM reserva_parametro WHERE user_id = %s", (uid,))
        apagar_usuario(esquema, uid)


def test_downgrade_sem_dados_remove_tudo_e_sobe_de_novo(esquema: str) -> None:
    cfg = Config(str(RAIZ / "alembic.ini"))
    with psycopg.connect(esquema) as vazio:  # tabela vazia: nenhum resíduo de outros testes
        linha = vazio.execute("SELECT count(*) FROM reserva_parametro").fetchone()
        assert linha == (0,)
    try:
        command.downgrade(cfg, "0009")
        assert _revisao(esquema) == "0009"
        assert _existentes(esquema) == ([], [])
    finally:
        command.upgrade(cfg, "head")
    assert _revisao(esquema) == "0011"
    assert _existentes(esquema) == (
        sorted(FUNCOES),
        ["reserva_parametro", "reserva_parametro_vigente"],
    )


def test_leitura_funciona_depois_de_subir_de_novo(conn: psycopg.Connection) -> None:
    uid = novo_usuario(conn)
    nova_reserva(conn, uid, "caixinha", {"data": "2026-01-01", "valor": "100.00"})
    assert situacao(conn, uid, "2026-04-01")["saldo_liquido"] == dec("100.00")
