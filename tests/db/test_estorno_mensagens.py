"""Mensagens de erro das funções do estorno são literais: sem valor interpolado (`||`, variável).

Mensagem de erro com dado do usuário vai parar em log e na resposta da API (PII/dado financeiro
nunca em log, `.claude/rules/seguranca.md`). Checagem estática sobre o SQL da migração 0007.
"""

from __future__ import annotations

import importlib.util
import re
from pathlib import Path
from types import ModuleType

RAIZ = Path(__file__).resolve().parents[2]
FUNCOES = (
    "SQL_ESTORNO_GUARDA",
    "SQL_ESTORNO_GRAVAR",
    "SQL_LANCAMENTO_GRAVAR",
    "SQL_LANCAMENTO_EXCLUIR",
)
LITERAL = re.compile(r"'(?:[^']|'')*'")


def _migracao() -> ModuleType:
    spec = importlib.util.spec_from_file_location(
        "migracao_0007", RAIZ / "db" / "migrations" / "versions" / "0007_estorno.py"
    )
    assert spec is not None and spec.loader is not None
    modulo = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(modulo)
    return modulo


def argumentos_de_abako_erro(sql: str) -> list[str]:
    """Texto entre os parênteses de cada `abako_erro(...)`, respeitando literais entre aspas."""
    chamadas: list[str] = []
    for achado in re.finditer(r"abako_erro\(", sql):
        i, nivel, aspas = achado.end(), 1, False
        while nivel:
            c = sql[i]
            if c == "'":
                aspas = not aspas
            elif not aspas and c == "(":
                nivel += 1
            elif not aspas and c == ")":
                nivel -= 1
            i += 1
        chamadas.append(sql[achado.end() : i - 1])
    return chamadas


def so_literais(argumentos: str) -> bool:
    """Verdadeiro se, tirados os literais entre aspas, sobra só vírgula e espaço."""
    return LITERAL.sub("", argumentos).strip(" \t\r\n,") == ""


def test_mensagens_de_abako_erro_sao_literais() -> None:
    modulo = _migracao()
    for nome in FUNCOES:
        sql = getattr(modulo, nome)
        chamadas = argumentos_de_abako_erro(sql)
        if nome in ("SQL_ESTORNO_GUARDA", "SQL_ESTORNO_GRAVAR"):
            assert chamadas, f"{nome}: nenhuma chamada de abako_erro encontrada"
        for argumentos in chamadas:
            assert "||" not in argumentos, f"{nome}: interpolação em {argumentos!r}"
            assert so_literais(argumentos), f"{nome}: argumento não literal em {argumentos!r}"


def test_a_checagem_pega_interpolacao() -> None:
    """A própria checagem não é vacuosa: acusa `||` e variável, aceita literais concatenados."""
    ruim = "PERFORM abako_erro('AB422', 'valor ' || v_total);"
    ruim2 = "PERFORM abako_erro('AB422', v_mensagem);"
    bom = "PERFORM abako_erro('AB422', 'a (parte) ' 'paga');"
    assert "||" in argumentos_de_abako_erro(ruim)[0]
    assert not so_literais(argumentos_de_abako_erro(ruim)[0])
    assert not so_literais(argumentos_de_abako_erro(ruim2)[0])
    assert so_literais(argumentos_de_abako_erro(bom)[0])
