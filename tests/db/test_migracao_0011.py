"""SPEC-010 / ADR 048: a 0011 (recorrentes e R2) — downgrade recusa com dados, sem dados reverte."""

from __future__ import annotations

from pathlib import Path

import psycopg
import pytest
from alembic import command
from alembic.config import Config

from tests.db.util_lancamento import apagar_usuario
from tests.db.util_r2 import (
    definir_horizonte,
    definir_vencimento,
    novo_cartao,
    recorrente,
    situacao,
    usuario_com_corrente,
)
from tests.db.util_saldo import dec

pytestmark = pytest.mark.banco

RAIZ = Path(__file__).resolve().parents[2]
FUNCOES = (
    "data_no_mes",
    "meses_entre",
    "ocorrencias_do_mes",
    "fatura_fechamento",
    "vencimento_fatura",
    "r2_horizonte",
    "pool_pago_ate",
    "alocacao_pago_ate",
    "r2_itens",
    "r2_situacao",
    "recorrente_gravar",
    "recorrente_excluir",
    "recorrente_vincular",
    "recorrente_desvincular",
    "r2_parametro_gravar",
    "vencimento_gravar",
)
TABELAS = (
    "cartao_vencimento",
    "r2_parametro",
    "r2_parametro_vigente",
    "recorrente",
    "recorrente_vigente",
    "recorrente_vinculo",
    "recorrente_vinculo_efetivo",
    "recorrente_vinculo_vigente",
    "vencimento_vigente",
)


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


def _revisao(url: str) -> str:
    with psycopg.connect(url) as conn:
        linha = conn.execute("SELECT version_num FROM alembic_version").fetchone()
    assert linha is not None
    return str(linha[0])


def test_downgrade_com_dados_e_recusado(esquema: str) -> None:
    """AC-12: com qualquer das quatro tabelas preenchida, voltar à 0010 é recusado e desfaz tudo."""
    cfg = Config(str(RAIZ / "alembic.ini"))
    for preencher in ("recorrente", "r2_parametro", "cartao_vencimento"):
        with psycopg.connect(esquema) as prep:
            uid, corrente = usuario_com_corrente(prep)
            if preencher == "recorrente":
                recorrente(prep, uid, "aluguel", "fixo", "10.00", 5, corrente, "2026-05")
            elif preencher == "r2_parametro":
                definir_horizonte(prep, uid, 12, "2026-01-01")
            else:
                definir_vencimento(prep, uid, novo_cartao(prep, uid, 10, None), 20, "2026-01-01")
            prep.commit()
        try:
            with pytest.raises(Exception, match="0011"):
                command.downgrade(cfg, "0010")
            assert _revisao(esquema) == "0014"
            assert _existentes(esquema) == (sorted(FUNCOES), sorted(TABELAS))
            with psycopg.connect(esquema) as ver:  # o dado continua lá
                linha = ver.execute(
                    f"SELECT count(*) FROM {preencher} WHERE user_id = %s",  # noqa: S608
                    (uid,),
                ).fetchone()
                assert linha == (1,)
        finally:
            apagar_usuario(esquema, uid)


def test_downgrade_sem_dados_remove_tudo_e_sobe_de_novo(esquema: str) -> None:
    cfg = Config(str(RAIZ / "alembic.ini"))
    with psycopg.connect(esquema) as vazio:  # tabelas vazias: nenhum resíduo de outros testes
        for tabela in ("recorrente", "recorrente_vinculo", "r2_parametro", "cartao_vencimento"):
            linha = vazio.execute(f"SELECT count(*) FROM {tabela}").fetchone()  # noqa: S608
            assert linha == (0,), tabela
    try:
        command.downgrade(cfg, "0010")
        assert _revisao(esquema) == "0010"
        assert _existentes(esquema) == ([], [])
    finally:
        command.upgrade(cfg, "head")
    assert _revisao(esquema) == "0014"
    assert _existentes(esquema) == (sorted(FUNCOES), sorted(TABELAS))


def test_leitura_funciona_depois_de_subir_de_novo(conn: psycopg.Connection) -> None:
    uid, _ = usuario_com_corrente(conn, "250.00")
    s = situacao(conn, uid, "2026-05-10")
    assert (s["horizonte_dias"], s["disponivel"], s["sobra"]) == (10, dec("250.00"), dec("250.00"))
