"""Mensagens de erro da 0010 são literais: sem nome, valor ou id interpolado (`||`, variável).

Checagem estática sobre o SQL da migração 0010. A escrita (`SECURITY DEFINER`) usa `abako_erro`
com literais; a leitura (`INVOKER`, que o app não pode passar por `abako_erro`) levanta o erro
direto, com `ERRCODE` e `MESSAGE` literais.
"""

from __future__ import annotations

import importlib.util
import re
from pathlib import Path
from types import ModuleType

from tests.db.test_estorno_mensagens import argumentos_de_abako_erro, so_literais

RAIZ = Path(__file__).resolve().parents[2]
ARQUIVO = RAIZ / "db" / "migrations" / "versions" / "0010_reserva.py"
RAISE_LITERAL = re.compile(
    r"RAISE EXCEPTION USING ERRCODE = '[A-Z0-9]{5}', MESSAGE = '(?:[^']|'')*';"
)
SQLS = ("SQL_NIVEL", "SQL_COBERTURA", "SQL_APORTE", "SQL_MESES_ATE", "SQL_GRAVAR", "SQL_SITUACAO")


def _migracao() -> ModuleType:
    spec = importlib.util.spec_from_file_location("migracao_0010", ARQUIVO)
    assert spec is not None and spec.loader is not None
    modulo = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(modulo)
    return modulo


def test_mensagens_de_erro_da_0010_sao_literais() -> None:
    modulo = _migracao()
    chamadas = raises = 0
    for nome in SQLS:
        sql = getattr(modulo, nome)
        for argumentos in argumentos_de_abako_erro(sql):
            chamadas += 1
            assert "||" not in argumentos, f"{nome}: interpolação em {argumentos!r}"
            assert so_literais(argumentos), f"{nome}: argumento não literal em {argumentos!r}"
        for trecho in re.findall(r"RAISE\b[^;]*;", sql):
            raises += 1
            assert RAISE_LITERAL.fullmatch(trecho), f"{nome}: RAISE não literal: {trecho!r}"
    assert chamadas >= 5, "esperava os abako_erro de validação de reserva_parametro_gravar"
    assert raises >= 1, "esperava o RAISE de data de hoje ausente em reserva_situacao"


def test_escrita_e_definer_com_search_path_fixo_e_leitura_e_invoker() -> None:
    modulo = _migracao()
    assert "SECURITY DEFINER SET search_path = public, pg_temp" in modulo.SQL_GRAVAR
    assert "SECURITY DEFINER" not in modulo.SQL_SITUACAO
    assert "||" not in modulo.SQL_GRAVAR and "||" not in modulo.SQL_SITUACAO
