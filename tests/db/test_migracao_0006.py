"""ADR 043: a 0006 é irreversível com cartão ou compra a crédito; o downgrade se recusa."""

from __future__ import annotations

from pathlib import Path

import psycopg
import pytest
from alembic import command
from alembic.config import Config

from tests.db.util_lancamento import apagar_usuario, cartao, compra, linha_credito
from tests.db.util_saldo import novo_usuario

pytestmark = pytest.mark.banco

RAIZ = Path(__file__).resolve().parents[2]


def _funcoes(url: str, nome: str) -> list[int]:
    """Quantidade de argumentos de cada assinatura existente da função `nome`."""
    with psycopg.connect(url) as conn:
        linhas = conn.execute(
            "SELECT pronargs FROM pg_proc WHERE proname = %s ORDER BY pronargs", (nome,)
        ).fetchall()
    return [int(r[0]) for r in linhas]


def test_downgrade_sem_dados_restaura_funcoes_antigas_e_sobe_de_novo(esquema: str) -> None:
    cfg = Config(str(RAIZ / "alembic.ini"))
    try:
        command.downgrade(cfg, "0005")
        with psycopg.connect(esquema) as ver:
            assert ver.execute("SELECT version_num FROM alembic_version").fetchone() == ("0005",)
        # assinaturas da 0005: sem o parâmetro final; as funções do cartão deixam de existir
        assert _funcoes(esquema, "conta_gravar") == [6]
        assert _funcoes(esquema, "lancamento_gravar") == [13]
        assert _funcoes(esquema, "fatura_total") == []
        assert _funcoes(esquema, "limite_linha") == []
        # a função antiga funciona e recusa o tipo que só existe na 0006
        with psycopg.connect(esquema) as c:
            uid = novo_usuario(c)
            ok = c.execute(
                "SELECT versao FROM conta_gravar(%s, NULL, NULL, 'a', 'corrente', NULL)", (uid,)
            ).fetchone()
            assert ok == (1,)
            with pytest.raises(psycopg.Error, match="tipo de conta inválido"):
                c.execute("SELECT conta_gravar(%s, NULL, NULL, 'b', 'divida', NULL)", (uid,))
            c.rollback()
    finally:
        command.upgrade(cfg, "head")
    with psycopg.connect(esquema) as ver:
        assert ver.execute("SELECT version_num FROM alembic_version").fetchone() == ("0008",)
    assert _funcoes(esquema, "conta_gravar") == [7]
    assert _funcoes(esquema, "lancamento_gravar") == [15]
    assert _funcoes(esquema, "fatura_total") == [3]
    assert _funcoes(esquema, "limite_linha") == [3]


def test_downgrade_com_cartao_e_recusado(esquema: str) -> None:
    with psycopg.connect(esquema) as prep:
        uid = novo_usuario(prep)
        linha, _ = linha_credito(prep, uid, "linha", "1000.00")
        c = cartao(prep, uid, "cartao", linha, 10, "2000-01-01")
        compra(prep, uid, c, "2025-03-05", "30.00", 3)
        prep.commit()
    try:
        with pytest.raises(Exception, match="apagaria dados"):
            command.downgrade(Config(str(RAIZ / "alembic.ini")), "0005")
        with psycopg.connect(esquema) as ver:
            versao = ver.execute("SELECT version_num FROM alembic_version").fetchone()
            parcelas = ver.execute(
                "SELECT count(*) FROM transacao_versao WHERE user_id = %s", (uid,)
            ).fetchone()
        assert versao == ("0008",)  # a falha na 0006 desfaz também o downgrade da 0008 e da 0007
        assert parcelas == (3,)  # as três parcelas continuam lá
    finally:
        apagar_usuario(esquema, uid)
