"""Mensagens de erro da 0011 são literais: sem nome, valor ou id interpolado (`||`, variável).

Checagem estática sobre o SQL da migração 0011 (SPEC-010, ADR 048). A escrita (`SECURITY DEFINER`)
usa `abako_erro` com literais; a leitura (`INVOKER`) levanta o erro direto, com `ERRCODE` e
`MESSAGE` literais.
"""

from __future__ import annotations

import importlib.util
import re
from pathlib import Path
from types import ModuleType

from tests.db.test_estorno_mensagens import argumentos_de_abako_erro, so_literais

RAIZ = Path(__file__).resolve().parents[2]
ARQUIVO = RAIZ / "db" / "migrations" / "versions" / "0011_recorrentes_r2.py"
RAISE_LITERAL = re.compile(
    r"RAISE EXCEPTION USING ERRCODE = '[A-Z0-9]{5}', MESSAGE = '(?:[^']|'')*';"
)
ESCRITA = (
    "SQL_R2_PARAMETRO_GRAVAR",
    "SQL_VENCIMENTO_GRAVAR",
    "SQL_RECORRENTE_GRAVAR",
    "SQL_RECORRENTE_EXCLUIR",
    "SQL_RECORRENTE_VINCULAR",
    "SQL_RECORRENTE_DESVINCULAR",
)
LEITURA = (
    "SQL_DATA_NO_MES",
    "SQL_MESES_ENTRE",
    "SQL_OCORRENCIAS",
    "SQL_FATURA_FECHAMENTO",
    "SQL_VENCIMENTO_FATURA",
    "SQL_R2_HORIZONTE",
    "SQL_POOL_PAGO_ATE",
    "SQL_ALOCACAO_PAGO_ATE",
    "SQL_R2_ITENS",
    "SQL_R2_SITUACAO",
)


def _migracao() -> ModuleType:
    spec = importlib.util.spec_from_file_location("migracao_0011", ARQUIVO)
    assert spec is not None and spec.loader is not None
    modulo = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(modulo)
    return modulo


def test_mensagens_de_erro_da_0011_sao_literais() -> None:
    modulo = _migracao()
    chamadas = raises = 0
    for nome in (*ESCRITA, *LEITURA):
        sql = getattr(modulo, nome)
        assert "||" not in sql, f"{nome}: concatenação no SQL"
        for argumentos in argumentos_de_abako_erro(sql):
            chamadas += 1
            assert "||" not in argumentos, f"{nome}: interpolação em {argumentos!r}"
            assert so_literais(argumentos), f"{nome}: argumento não literal em {argumentos!r}"
        for trecho in re.findall(r"RAISE\b[^;]*;", sql):
            raises += 1
            assert RAISE_LITERAL.fullmatch(trecho), f"{nome}: RAISE não literal: {trecho!r}"
    assert chamadas >= 30, "esperava os abako_erro de validação das funções de escrita"
    assert raises == 2, "esperava o RAISE de data de hoje ausente em r2_itens e r2_situacao"


def test_escrita_e_definer_com_search_path_fixo_e_leitura_e_invoker() -> None:
    modulo = _migracao()
    for nome in ESCRITA:
        sql = getattr(modulo, nome)
        assert "SECURITY DEFINER SET search_path = public, pg_temp" in sql, nome
    for nome in LEITURA:
        assert "SECURITY DEFINER" not in getattr(modulo, nome), nome
