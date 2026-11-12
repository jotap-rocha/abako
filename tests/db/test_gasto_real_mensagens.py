"""Mensagens de erro da 0009 são literais: sem nome, valor ou id interpolado (`||`, variável).

Mensagem de erro com dado do usuário vai parar em log e na resposta da API. Checagem estática
sobre o SQL da migração 0009 (a função não usa `abako_erro`, que o app não executa: levanta o
erro direto, com `ERRCODE` e `MESSAGE` literais).
"""

from __future__ import annotations

import importlib.util
import re
from pathlib import Path
from types import ModuleType

from tests.db.test_estorno_mensagens import argumentos_de_abako_erro

RAIZ = Path(__file__).resolve().parents[2]
ARQUIVO = RAIZ / "db" / "migrations" / "versions" / "0009_gasto_real.py"
RAISE_LITERAL = re.compile(
    r"RAISE EXCEPTION USING ERRCODE = '[A-Z0-9]{5}', MESSAGE = '(?:[^']|'')*';"
)


def _migracao() -> ModuleType:
    spec = importlib.util.spec_from_file_location("migracao_0009", ARQUIVO)
    assert spec is not None and spec.loader is not None
    modulo = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(modulo)
    return modulo


def _todo_sql(modulo: ModuleType) -> dict[str, str]:
    return {
        "SQL_MES_INICIO": modulo.SQL_MES_INICIO,
        "SQL_GASTO_REAL_ITENS": modulo.SQL_GASTO_REAL_ITENS,
        "SQL_GASTO_REAL": modulo.SQL_GASTO_REAL,
        "SQL_GASTO_REAL_POR_CONTA": modulo.SQL_GASTO_REAL_POR_CONTA,
        "receita_caixa": modulo._sql_receita("receita_caixa", beneficio=False),
        "receita_beneficio": modulo._sql_receita("receita_beneficio", beneficio=True),
        "SQL_RECEITA_TOTAL": modulo.SQL_RECEITA_TOTAL,
    }


def test_mensagens_de_erro_da_0009_sao_literais() -> None:
    modulo = _migracao()
    sqls = _todo_sql(modulo)
    raises = 0
    for nome, sql in sqls.items():
        # nenhuma chamada de abako_erro com interpolação (o app não a executa; fica o teste)
        for argumentos in argumentos_de_abako_erro(sql):
            assert "||" not in argumentos, f"{nome}: interpolação em {argumentos!r}"
        for trecho in re.findall(r"RAISE\b[^;]*;", sql):
            raises += 1
            assert RAISE_LITERAL.fullmatch(trecho), f"{nome}: RAISE não literal: {trecho!r}"
    assert raises >= 1, "esperava ao menos o RAISE de mês inválido em mes_inicio"
    assert "RAISE" in sqls["SQL_MES_INICIO"]
