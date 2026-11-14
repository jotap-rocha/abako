"""SPEC-014-AC-1 (INV-15): o pipeline escreve só no analítico e o analítico só tem agregados."""

from __future__ import annotations

import ast
import re
from collections.abc import Callable
from pathlib import Path

import duckdb
import psycopg
import pytest

from pipeline import esquema, extracao
from pipeline import executar as executar_modulo
from pipeline.config import Config
from pipeline.executar import SUCESSO, executar
from tests.pipeline.util_pipeline import Cenario, retrato_do_transacional, tabelas_do_arquivo

pytestmark = pytest.mark.banco

TABELAS_ESPERADAS = {
    "saldo_diario",
    "gasto_mensal",
    "fatura_resumo",
    "limite_linha",
    "cobertura_reserva",
    "a_receber",
    "execucao",
}
# O que o analítico nunca pode ter como coluna: texto livre, nomes e valor de transação.
COLUNAS_PROIBIDAS = {"descricao", "nome", "valor", "transacao_id", "pessoa_id", "estabelecimento"}


def test_nao_escreve_no_transacional(
    esquema: str,
    url_pipeline: str,
    fazer_config: Callable[..., Config],
    cenario: Cenario,
) -> None:
    """Escritas com o papel são recusadas (transação somente leitura ou falta de privilégio;
    a ausência de GRANT em si é provada em test_papel.py) e o transacional fica idêntico."""
    with psycopg.connect(url_pipeline) as pipe:
        comandos = (
            "INSERT INTO usuario (login) VALUES ('x_pipeline')",
            "UPDATE transacao_versao SET valor = 0",
            "DELETE FROM conta_versao",
            "TRUNCATE snapshot_saldo",
            "CREATE TABLE intruso (id int)",
            "SELECT conta_gravar(1, NULL, NULL, 'x', 'corrente', NULL)",
        )
        for comando in comandos:
            with pytest.raises(
                (psycopg.errors.ReadOnlySqlTransaction, psycopg.errors.InsufficientPrivilege)
            ):
                pipe.execute(comando)
            pipe.rollback()

    antes = retrato_do_transacional(esquema)
    assert antes["transacao_versao"][0] > 0  # o cenário existe: a prova não é vazia
    config = fazer_config()
    assert executar(config) == SUCESSO
    assert config.arquivo.is_file()
    depois = retrato_do_transacional(esquema)
    assert depois == antes
    assert "intruso" not in depois


def test_analitico_so_tem_agregados(fazer_config: Callable[..., Config], cenario: Cenario) -> None:
    """Sem linhas de transação: só as tabelas agregadas, sem coluna de texto livre ou de valor
    de lançamento (saldo_diario tem uma linha por conta e dia, não por transação)."""
    config = fazer_config()
    assert executar(config) == SUCESSO
    con = duckdb.connect(str(config.arquivo), read_only=True)
    try:
        nomes = {r[0] for r in con.execute("SHOW TABLES").fetchall()}
        assert nomes == TABELAS_ESPERADAS
        colunas = {
            r[0]
            for r in con.execute(
                "SELECT column_name FROM duckdb_columns() WHERE NOT internal"
            ).fetchall()
        }
        assert not (colunas & COLUNAS_PROIBIDAS), colunas & COLUNAS_PROIBIDAS
        # nenhuma coluna de texto além de códigos curtos gerados pelo banco
        textos = {
            (r[0], r[1])
            for r in con.execute(
                "SELECT table_name, column_name FROM duckdb_columns() "
                "WHERE NOT internal AND data_type = 'VARCHAR'"
            ).fetchall()
        }
        assert textos == {
            ("gasto_mensal", "mes"),
            ("fatura_resumo", "competencia"),
            ("cobertura_reserva", "nivel"),
            ("execucao", "ambiente"),
        }
        tipos_dinheiro = {
            r[0]
            for r in con.execute(
                "SELECT data_type FROM duckdb_columns() "
                "WHERE NOT internal "
                "AND column_name IN ('saldo', 'gasto', 'total', 'limite', 'meta')"
            ).fetchall()
        }
        assert tipos_dinheiro == {"DECIMAL(18,2)"}  # nunca float (INV-14)
    finally:
        con.close()


def test_sem_nome_nem_descricao_no_arquivo(
    fazer_config: Callable[..., Config], cenario: Cenario, esquema: str
) -> None:
    """Varredura do conteúdo (valores e bytes do arquivo) atrás dos marcadores de nome/descrição."""
    # controle: os marcadores existem de verdade no transacional (a varredura não é vazia)
    with psycopg.connect(esquema) as c:
        achados = c.execute(
            "SELECT (SELECT count(*) FROM transacao_versao WHERE descricao LIKE 'MARC%%'), "
            "(SELECT count(*) FROM conta_versao WHERE nome LIKE 'MARC%%'), "
            "(SELECT count(*) FROM pessoa WHERE nome LIKE 'MARC%%'), "
            "(SELECT count(*) FROM linha_credito WHERE nome LIKE 'MARC%%')"
        ).fetchone()
        c.rollback()
    assert achados is not None and all(n > 0 for n in achados)

    config = fazer_config()
    assert executar(config) == SUCESSO
    for tabela, linhas in tabelas_do_arquivo(config.arquivo).items():
        for linha in linhas:
            assert "MARC" not in repr(linha), tabela
    assert b"MARC" not in config.arquivo.read_bytes()


def _literais_fora_de_docstring(arquivo: Path) -> list[str]:
    arvore = ast.parse(arquivo.read_text(encoding="utf-8"))
    docstrings: set[int] = set()
    for no in ast.walk(arvore):
        if isinstance(no, ast.Module | ast.FunctionDef | ast.AsyncFunctionDef | ast.ClassDef):
            if ast.get_docstring(no, clean=False) is not None:
                primeiro = no.body[0]
                assert isinstance(primeiro, ast.Expr)
                docstrings.add(id(primeiro.value))
    return [
        n.value
        for n in ast.walk(arvore)
        if isinstance(n, ast.Constant) and isinstance(n.value, str) and id(n) not in docstrings
    ]


def test_consultas_do_pipeline_nao_selecionam_texto_livre() -> None:
    """Estático: nenhum literal do pipeline cita `descricao`, coluna `nome` ou `login`, nem usa
    `SELECT *` / `x.*` (que traria colunas de texto sem citá-las)."""
    modulos = (extracao, executar_modulo, esquema)
    total = 0
    for modulo in modulos:
        literais = _literais_fora_de_docstring(Path(str(modulo.__file__)))
        total += len(literais)
        for texto in literais:
            limpo = texto.replace("count(*)", "")
            proibido = r"descricao|\bnome\b|login"
            if re.search(r"\bselect\b", limpo, re.IGNORECASE):
                proibido += r"|\*"  # `SELECT *` ou `x.*` em qualquer consulta
            assert not re.search(proibido, limpo, re.IGNORECASE), (modulo.__name__, texto)
    assert total > 20  # a varredura leu SQL de verdade
