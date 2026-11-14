"""SPEC-013 / ADR 052: a 0013 (vale) — downgrade recusa com dado, sem dado volta à 0012."""

from __future__ import annotations

from pathlib import Path

import psycopg
import pytest
from alembic import command
from alembic.config import Config

from tests.db.util_lancamento import apagar_usuario, conta
from tests.db.util_saldo import dia, novo_usuario
from tests.db.util_vale import decidir, gasto, novo_vale

pytestmark = pytest.mark.banco

RAIZ = Path(__file__).resolve().parents[2]
TABELAS = ("vale_bolso", "vale_decisao", "vale_decisao_vigente", "vale_parametro")
FUNCOES = (
    "beneficios_contas",
    "vale_calculo",
    "vale_conta_em",
    "vale_mes",
    "vale_decisao_gravar",
    "vale_parametro_gravar",
    "vale_situacao",
)


def _revisao(url: str) -> str:
    with psycopg.connect(url) as conn:
        linha = conn.execute("SELECT version_num FROM alembic_version").fetchone()
    assert linha is not None
    return str(linha[0])


def _existentes(url: str) -> tuple[list[str], list[str]]:
    with psycopg.connect(url) as conn:
        funcoes = conn.execute(
            "SELECT proname FROM pg_proc WHERE proname = ANY(%s) ORDER BY proname", (list(FUNCOES),)
        ).fetchall()
        tabelas = conn.execute(
            "SELECT relname FROM pg_class WHERE relname = ANY(%s) ORDER BY relname",
            (list(TABELAS),),
        ).fetchall()
    return [r[0] for r in funcoes], [r[0] for r in tabelas]


def _assinaturas(url: str) -> tuple[int, int]:
    """(argumentos de lancamento_gravar, colunas de alertas)."""
    with psycopg.connect(url) as conn:
        linha = conn.execute(
            "SELECT pronargs FROM pg_proc WHERE proname = 'lancamento_gravar'"
        ).fetchone()
        assert linha is not None
        uid = novo_usuario(conn)
        cur = conn.execute("SELECT * FROM alertas(%s, DATE '2026-05-10')", (uid,))
        colunas = len(cur.description or [])
        conn.rollback()
    return int(linha[0]), colunas


def test_downgrade_recusa_com_dados(esquema: str) -> None:
    """Com parâmetro, bolso ou decisão gravados, voltar à 0012 é recusado e desfaz tudo."""
    cfg = Config(str(RAIZ / "alembic.ini"))
    for restante in ("vale_parametro", "vale_bolso", "vale_decisao"):
        with psycopg.connect(esquema) as prep:
            v = novo_vale(prep)
            gasto(prep, v.uid, v.vr, "2025-01-10", "10.00", "trabalho")
            decidir(prep, v.uid, "2025-01", "pessoal")
            if restante != "vale_parametro":  # deixa só a tabela que o caso testa
                for outra in ("vale_parametro", "vale_bolso", "vale_decisao"):
                    if outra != restante:
                        prep.execute(f"DELETE FROM {outra} WHERE user_id = %s", (v.uid,))  # noqa: S608
            else:
                prep.execute("DELETE FROM vale_bolso WHERE user_id = %s", (v.uid,))
                prep.execute("DELETE FROM vale_decisao WHERE user_id = %s", (v.uid,))
            prep.commit()
        try:
            with pytest.raises(Exception, match="0013"):
                command.downgrade(cfg, "0012")
            assert _revisao(esquema) == "0013"  # a recusa desfaz tudo: nada foi removido
            assert _existentes(esquema) == (sorted(FUNCOES), sorted(TABELAS))
            with psycopg.connect(esquema) as ver:  # o dado continua lá
                linha = ver.execute(
                    f"SELECT count(*) FROM {restante} WHERE user_id = %s",  # noqa: S608
                    (v.uid,),
                ).fetchone()
                assert linha == (1,)
        finally:
            apagar_usuario(esquema, v.uid)


def test_downgrade_sem_dados_volta_a_0012_e_sobe_de_novo(esquema: str) -> None:
    cfg = Config(str(RAIZ / "alembic.ini"))
    with psycopg.connect(esquema) as vazio:  # nenhum resíduo de outros testes
        for tabela in ("vale_parametro", "vale_bolso", "vale_decisao"):
            linha = vazio.execute(f"SELECT count(*) FROM {tabela}").fetchone()  # noqa: S608
            assert linha == (0,), tabela
    assert _assinaturas(esquema) == (16, 29)
    try:
        command.downgrade(cfg, "0012")
        assert _revisao(esquema) == "0012"
        assert _existentes(esquema) == ([], [])
        assert _assinaturas(esquema) == (15, 24)  # as definições da 0008 e da 0012
        with psycopg.connect(esquema) as c:  # a escrita de 15 argumentos segue funcionando
            uid = novo_usuario(c)
            corrente = conta(c, uid, "corrente")
            criado = c.execute(
                "SELECT criado FROM lancamento_gravar(%s, NULL, NULL, 'debito', DATE '2025-01-10', "
                "5.00, %s, NULL, NULL, NULL, NULL, NULL, NULL, NULL, NULL)",
                (uid, corrente),
            ).fetchone()
            assert criado == (True,)
            c.rollback()
    finally:
        command.upgrade(cfg, "head")
    assert _revisao(esquema) == "0013"
    assert _existentes(esquema) == (sorted(FUNCOES), sorted(TABELAS))
    assert _assinaturas(esquema) == (16, 29)


def test_leitura_e_escrita_funcionam_depois_de_subir_de_novo(conn: psycopg.Connection) -> None:
    v = novo_vale(conn)
    gasto(conn, v.uid, v.vr, "2025-01-10", "10.00", "trabalho")
    linha = conn.execute(
        "SELECT consumo_trabalho FROM vale_situacao(%s, '2025-01', %s)", (v.uid, dia("2025-12-15"))
    ).fetchone()
    assert linha is not None and str(linha[0]) == "10.00"
