"""Mensagens de erro da 0008 são literais: sem nome, valor ou id interpolado (`||`, variável).

O nome de terceiro é dado pessoal (ADR 045): mensagem de erro com dado do usuário vai parar em log
e na resposta da API. Checagem estática sobre o SQL da migração 0008, com os mesmos auxiliares da
checagem da 0007.
"""

from __future__ import annotations

import importlib.util
from pathlib import Path
from types import ModuleType

from tests.db.test_estorno_mensagens import argumentos_de_abako_erro, so_literais

RAIZ = Path(__file__).resolve().parents[2]
ARQUIVO = RAIZ / "db" / "migrations" / "versions" / "0008_terceiros_repasse.py"
FUNCOES = (
    "SQL_PESSOA_GRAVAR",
    "SQL_PESSOA_EXCLUIR",
    "SQL_LANCAMENTO_GRAVAR_BASE",
    "SQL_LANCAMENTO_GRAVAR",
    "SQL_LANCAMENTO_EXCLUIR_BASE",
)
COM_ERROS = ("SQL_PESSOA_GRAVAR", "SQL_PESSOA_EXCLUIR", "SQL_LANCAMENTO_GRAVAR_BASE")


def _migracao() -> ModuleType:
    spec = importlib.util.spec_from_file_location("migracao_0008", ARQUIVO)
    assert spec is not None and spec.loader is not None
    modulo = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(modulo)
    return modulo


def test_mensagens_de_abako_erro_da_0008_sao_literais() -> None:
    modulo = _migracao()
    for nome in FUNCOES:
        sql = getattr(modulo, nome)
        chamadas = argumentos_de_abako_erro(sql)
        if nome in COM_ERROS:
            assert chamadas, f"{nome}: nenhuma chamada de abako_erro encontrada"
        for argumentos in chamadas:
            assert "||" not in argumentos, f"{nome}: interpolação em {argumentos!r}"
            assert so_literais(argumentos), f"{nome}: argumento não literal em {argumentos!r}"
    # nenhuma outra forma de levantar erro com dado (RAISE ... %) nas funções novas
    for nome in FUNCOES:
        sql = getattr(modulo, nome)
        assert "RAISE" not in sql.replace("RAISE EXCEPTION USING ERRCODE = p_codigo", ""), nome
