"""Mensagens da 0013 são literais: sem valor, nome ou id interpolado (`||`, variável).

Checagem estática sobre o SQL da migração 0013 (SPEC-013, ADR 052): todo `abako_erro` e todo
`RAISE` leva texto literal; as leituras são `INVOKER`, `STABLE`, com `search_path` fixo e sem
escrita; as escritas são `SECURITY DEFINER` com `search_path` fixo.
"""

from __future__ import annotations

import importlib.util
import re
from pathlib import Path
from types import ModuleType

RAIZ = Path(__file__).resolve().parents[2]
ARQUIVO = RAIZ / "db" / "migrations" / "versions" / "0013_vale.py"
ABAKO_ERRO = re.compile(r"abako_erro\(\s*'(AB4[0-9]{2})',\s*'((?:[^']|'')*)'\s*\)", re.S)
RAISE_LITERAL = re.compile(
    r"RAISE EXCEPTION USING ERRCODE = '[A-Z0-9]{5}', MESSAGE = '(?:[^']|'')*';"
)
LEITURAS = (
    "SQL_CONTA_EM",
    "SQL_MES",
    "SQL_CALCULO",
    "SQL_SITUACAO",
    "SQL_BENEFICIOS",
    "SQL_ALERTAS",
)
ESCRITAS = ("SQL_PARAMETRO_GRAVAR", "SQL_DECISAO_GRAVAR", "SQL_LANCAMENTO_GRAVAR")


def _modulo() -> ModuleType:
    spec = importlib.util.spec_from_file_location("migracao_0013", ARQUIVO)
    assert spec is not None and spec.loader is not None
    modulo = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(modulo)
    return modulo


def _sql(nomes: tuple[str, ...]) -> str:
    m = _modulo()
    return "\n".join(getattr(m, n) for n in nomes)


def test_mensagens_da_0013_sao_literais() -> None:
    sql = _sql((*LEITURAS, *ESCRITAS))
    assert "||" not in sql, "concatenação no SQL"
    assert "format(" not in sql.lower() and "concat" not in sql.lower()
    sem_comentario = re.sub(r"--[^\n]*", "", sql)
    # toda chamada a abako_erro tem código e mensagem literais, sem interpolação
    chamadas = sem_comentario.count("abako_erro(")
    achadas = ABAKO_ERRO.findall(sem_comentario)
    assert chamadas == len(achadas) and chamadas >= 14, (chamadas, len(achadas))
    for _, mensagem in achadas:
        assert "%" not in mensagem and "{" not in mensagem, mensagem
    raises = re.findall(r"RAISE\b[^;]*;", sem_comentario)
    assert raises, "esperava os RAISE de data de hoje ausente"
    for r in raises:
        assert RAISE_LITERAL.fullmatch(r), r


def test_leituras_do_vale_sao_invoker_e_sem_escrita() -> None:
    for nome in LEITURAS:
        sql = _sql((nome,)).upper()
        assert "SECURITY DEFINER" not in sql, nome
        assert "STABLE" in sql, nome
        assert "SET SEARCH_PATH = PUBLIC, PG_TEMP" in sql, nome
        for comando in ("INSERT ", "UPDATE ", "DELETE ", "TRUNCATE", "CREATE TABLE"):
            assert comando not in sql, (nome, comando)
    for nome in ESCRITAS:
        sql = _sql((nome,)).upper()
        assert "SECURITY DEFINER SET SEARCH_PATH = PUBLIC, PG_TEMP" in sql, nome
