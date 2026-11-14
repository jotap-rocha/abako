"""SPEC-007 / ADR 045: a 0008 (terceiros e repasse) — reversão e compatibilidade da assinatura."""

from __future__ import annotations

from pathlib import Path

import psycopg
import pytest
from alembic import command
from alembic.config import Config

from tests.db.test_estorno import DATA_COMPRA, montar
from tests.db.util_lancamento import apagar_usuario, compra, lancar
from tests.db.util_saldo import dia, novo_usuario
from tests.db.util_terceiros import nova_pessoa

pytestmark = pytest.mark.banco

RAIZ = Path(__file__).resolve().parents[2]


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


def _existe(url: str, consulta: str) -> bool:
    with psycopg.connect(url) as conn:
        linha = conn.execute(consulta).fetchone()
    assert linha is not None
    return bool(linha[0])


def _gravar_14(
    conn: psycopg.Connection,
    uid: int,
    tipo: str,
    conta_id: int,
    valor: str,
    parcelas: int | None = None,
) -> tuple[int, bool]:
    """Chamada de 14 argumentos, a única que existe na 0007."""
    linha = conn.execute(
        "SELECT versao, criado FROM lancamento_gravar(%s, NULL, NULL, %s, %s, %s, %s, NULL, "
        "NULL, NULL, NULL, NULL, NULL, %s)",
        (uid, tipo, dia("2025-03-05"), valor, conta_id, parcelas),
    ).fetchone()
    assert linha is not None
    return int(linha[0]), bool(linha[1])


def test_downgrade_sem_dados_restaura_a_0007_e_sobe_de_novo(esquema: str) -> None:
    cfg = Config(str(RAIZ / "alembic.ini"))
    try:
        command.downgrade(cfg, "0007")
        assert _revisao(esquema) == "0007"
        assert not _existe(esquema, "SELECT to_regclass('pessoa') IS NOT NULL")
        assert _funcoes(esquema, "pessoa_gravar") == []
        assert _funcoes(esquema, "a_receber_pessoas") == []
        assert _funcoes(esquema, "fatura_resumo") == []
        assert _funcoes(esquema, "lancamento_gravar") == [14]
        assert _funcoes(esquema, "lancamento_gravar_base") == [14]
        assert _funcoes(esquema, "lancamento_excluir_base") == [3]
        assert not _existe(
            esquema,
            "SELECT EXISTS (SELECT 1 FROM information_schema.columns "
            "WHERE table_name = 'transacao_versao' AND column_name = 'pessoa_id')",
        )
        # a escrita da 0007 funciona (14 argumentos): o repasse volta a ser recusado
        with psycopg.connect(esquema) as c:
            cen = montar(c)
            ok = _gravar_14(c, cen.uid, "credito", cen.cartao, "30.00", 3)
            assert ok == (1, True)
            with pytest.raises(psycopg.Error, match="não está disponível"):
                _gravar_14(c, cen.uid, "repasse", cen.corrente, "10.00")
            c.rollback()
    finally:
        command.upgrade(cfg, "head")
    assert _revisao(esquema) == "0014"
    assert _funcoes(esquema, "lancamento_gravar") == [16]
    assert _funcoes(esquema, "lancamento_gravar_base") == [15]
    assert _funcoes(esquema, "pessoa_gravar") == [4]
    assert _funcoes(esquema, "fatura_itens") == [3]


def test_downgrade_com_terceiros_e_recusado(esquema: str) -> None:
    with psycopg.connect(esquema) as prep:
        cen = montar(prep)
        b = nova_pessoa(prep, cen.uid, "pessoa_b")
        compra(prep, cen.uid, cen.cartao, DATA_COMPRA, "30.00", 3, pessoa=b)
        lancar(prep, cen.uid, "repasse", "2025-03-20", cen.corrente, "10.00", pessoa=b)
        prep.commit()
    try:
        with pytest.raises(Exception, match="apagaria dados"):
            command.downgrade(Config(str(RAIZ / "alembic.ini")), "0007")
        assert _revisao(esquema) == "0014"
        with psycopg.connect(esquema) as ver:
            linha = ver.execute(
                "SELECT count(*) FROM transacao_versao "
                "WHERE user_id = %s AND pessoa_id IS NOT NULL",
                (cen.uid,),
            ).fetchone()
        assert linha == (4,)  # 3 parcelas e o repasse continuam lá
    finally:
        apagar_usuario(esquema, cen.uid)


def test_chamada_antiga_de_14_argumentos_continua_valendo(conn: psycopg.Connection) -> None:
    """A assinatura pública ganhou o 15º parâmetro com DEFAULT: quem chamava com 14 não quebra."""
    uid = novo_usuario(conn)
    corrente = conn.execute(
        "SELECT conta_id FROM conta_gravar(%s, NULL, NULL, 'c', 'corrente', NULL)", (uid,)
    ).fetchone()
    assert corrente is not None
    linha = conn.execute(
        "SELECT versao, criado FROM lancamento_gravar(%s, NULL, NULL, 'receita', %s, 10.00, %s, "
        "NULL, NULL, NULL, NULL, NULL, NULL, NULL)",
        (uid, dia("2025-03-05"), corrente[0]),
    ).fetchone()
    assert linha == (1, True)
