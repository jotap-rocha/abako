"""SPEC-006 / ADR 044: a 0007 (estorno) — reversão, restrições da tabela e papéis."""

from __future__ import annotations

from decimal import Decimal
from pathlib import Path

import psycopg
import pytest
from alembic import command
from alembic.config import Config

from tests.db.test_estorno import DATA_COMPRA, DATA_ESTORNO, estornar, montar
from tests.db.util_lancamento import apagar_usuario, compra

pytestmark = pytest.mark.banco

RAIZ = Path(__file__).resolve().parents[2]

FUNCOES_DO_APP = (
    "estorno_gravar(bigint, bigint, integer, date, text)",
    "pool_pago(bigint, bigint)",
    "alocacao_pago(bigint, bigint)",
    "compra_paga(bigint, bigint)",
    "lancamento_gravar(bigint, bigint, integer, text, date, numeric, bigint, bigint, numeric, "
    "numeric, text, text, text, integer, bigint)",
    "lancamento_excluir(bigint, bigint, integer)",
)
FUNCOES_FECHADAS = (
    "lancamento_gravar_base(bigint, bigint, integer, text, date, numeric, bigint, bigint, "
    "numeric, numeric, text, text, text, integer, bigint)",
    "lancamento_excluir_base(bigint, bigint, integer)",
    "estorno_guarda(bigint, bigint, text, bigint)",
    "cartao_trava(bigint, bigint)",
)


def _funcoes(url: str, nome: str) -> list[int]:
    with psycopg.connect(url) as conn:
        linhas = conn.execute(
            "SELECT pronargs FROM pg_proc WHERE proname = %s ORDER BY pronargs", (nome,)
        ).fetchall()
    return [int(r[0]) for r in linhas]


def _revisao(url: str) -> str:
    with psycopg.connect(url) as conn:
        linha = conn.execute("SELECT version_num FROM alembic_version").fetchone()
    assert linha is not None
    return str(linha[0])


def test_downgrade_sem_estorno_restaura_a_0006_e_sobe_de_novo(esquema: str) -> None:
    cfg = Config(str(RAIZ / "alembic.ini"))
    try:
        command.downgrade(cfg, "0006")
        assert _revisao(esquema) == "0006"
        assert _funcoes(esquema, "estorno_gravar") == []
        assert _funcoes(esquema, "lancamento_gravar_base") == []
        assert _funcoes(esquema, "lancamento_gravar") == [14]
        assert _funcoes(esquema, "lancamento_excluir") == [3]
        with psycopg.connect(esquema) as conn:
            colunas = conn.execute(
                "SELECT count(*) FROM information_schema.columns "
                "WHERE table_name = 'transacao_versao' AND column_name LIKE 'estorno_%'"
            ).fetchone()
            assert colunas == (0,)
    finally:
        command.upgrade(cfg, "head")
    assert _revisao(esquema) == "0010"
    assert _funcoes(esquema, "estorno_gravar") == [5]
    assert _funcoes(esquema, "lancamento_gravar_base") == [15]
    assert _funcoes(esquema, "lancamento_gravar") == [15]


def test_downgrade_com_estorno_e_recusado(esquema: str) -> None:
    with psycopg.connect(esquema) as prep:
        c = montar(prep)
        tid, versao, _ = compra(prep, c.uid, c.cartao, DATA_COMPRA, "30.00", 3)
        estornar(prep, c, tid, versao, DATA_ESTORNO)
        prep.commit()
    try:
        with pytest.raises(Exception, match="apagaria dados"):
            command.downgrade(Config(str(RAIZ / "alembic.ini")), "0006")
        assert _revisao(esquema) == "0010"
        with psycopg.connect(esquema) as ver:
            linha = ver.execute(
                "SELECT count(*) FROM transacao_versao WHERE user_id = %s AND tipo = 'estorno'",
                (c.uid,),
            ).fetchone()
        assert linha == (1,)
    finally:
        apagar_usuario(esquema, c.uid)


def test_restricoes_da_linha_de_estorno(conn: psycopg.Connection) -> None:
    """Credito > valor, estorno sem vínculo e segundo estorno vigente são barrados na tabela."""
    c = montar(conn)
    tid, versao, _ = compra(conn, c.uid, c.cartao, DATA_COMPRA, "400.00", 4)
    insert = (
        "INSERT INTO transacao_versao (user_id, tipo, conta_id, data_transacao, valor, "
        "competencia, estorno_de, estorno_credito) VALUES (%s, 'estorno', %s, DATE '2025-04-20', "
        "%s, '2025-05', %s, %s)"
    )
    for valores, erro in (
        ((c.uid, c.cartao, 400, tid, 400.01), psycopg.errors.CheckViolation),  # P > T
        ((c.uid, c.cartao, -400, tid, 0), psycopg.errors.CheckViolation),  # estorno é positivo
        ((c.uid, c.cartao, 400, None, 0), psycopg.errors.CheckViolation),  # sem vínculo
    ):
        with pytest.raises(erro), conn.transaction():
            conn.execute(insert, valores)
    estornar(conn, c, tid, versao)
    with pytest.raises(psycopg.errors.UniqueViolation), conn.transaction():
        conn.execute(insert, (c.uid, c.cartao, 400, tid, 0))
    # vínculo em linha que não é estorno também é barrado
    with pytest.raises(psycopg.errors.CheckViolation), conn.transaction():
        conn.execute(
            "INSERT INTO transacao_versao (user_id, tipo, conta_id, data_transacao, valor, "
            "estorno_de) VALUES (%s, 'receita', %s, DATE '2025-04-20', 1, %s)",
            (c.uid, c.corrente, tid),
        )


def test_papeis_do_estorno(esquema: str, url_app: str, url_pipeline: str) -> None:
    """`app` executa as funções do estorno e não escreve nas tabelas; `pipeline` só lê."""
    with psycopg.connect(url_app) as app, psycopg.connect(url_pipeline) as pipe:
        for funcao in FUNCOES_DO_APP:
            assert app.execute(
                "SELECT has_function_privilege(%s, 'EXECUTE')", (funcao,)
            ).fetchone() == (True,)
            assert pipe.execute(
                "SELECT has_function_privilege(%s, 'EXECUTE')", (funcao,)
            ).fetchone() == (False,)
        for funcao in FUNCOES_FECHADAS:
            assert app.execute(
                "SELECT has_function_privilege(%s, 'EXECUTE')", (funcao,)
            ).fetchone() == (False,)
            assert pipe.execute(
                "SELECT has_function_privilege(%s, 'EXECUTE')", (funcao,)
            ).fetchone() == (False,)
        for papel in (app, pipe):
            assert papel.execute(
                "SELECT has_table_privilege(current_user, 'parcela_ativa', 'SELECT')"
            ).fetchone() == (True,)
            for priv in ("INSERT", "UPDATE", "DELETE"):
                assert papel.execute(
                    "SELECT has_table_privilege(current_user, 'transacao_versao', %s)", (priv,)
                ).fetchone() == (False,)

        # o app estorna pela função (a SECURITY DEFINER escreve como dono); nada fica no banco
        uid = app.execute(
            "INSERT INTO usuario (login) VALUES ('u_papel_estorno') RETURNING user_id"
        ).fetchone()
        assert uid is not None
        u = uid[0]
        linha = app.execute(
            "SELECT linha_id FROM linha_credito_gravar(%s, NULL, NULL, 'l', 1000.00)", (u,)
        ).fetchone()
        assert linha is not None
        card = app.execute(
            "SELECT conta_id FROM conta_gravar(%s, NULL, NULL, 'c', 'divida', NULL, %s)",
            (u, linha[0]),
        ).fetchone()
        assert card is not None
        app.execute("SELECT fechamento_gravar(%s, %s, 10, DATE '2025-01-01')", (u, card[0]))
        lanc = app.execute(
            "SELECT transacao_id, versao FROM lancamento_gravar(%s, NULL, NULL, 'credito', "
            "DATE '2025-03-05', 90.00, %s, NULL, NULL, NULL, NULL, NULL, NULL, 3)",
            (u, card[0]),
        ).fetchone()
        assert lanc is not None
        est = app.execute(
            "SELECT total, credito, limite_devolvido FROM estorno_gravar(%s, %s, %s, "
            "DATE '2025-04-20', NULL)",
            (u, lanc[0], lanc[1]),
        ).fetchone()
        assert est is not None
        assert list(est) == [Decimal("90.00"), Decimal("0.00"), Decimal("90.00")]
        app.rollback()
        with pytest.raises(psycopg.errors.InsufficientPrivilege):
            pipe.execute("SELECT estorno_gravar(1, 1, 1, DATE '2025-04-20', NULL)")
        pipe.rollback()
