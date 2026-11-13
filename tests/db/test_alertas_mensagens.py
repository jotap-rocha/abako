"""Mensagens da 0012 são literais: sem valor, nome ou id interpolado (`||`, variável).

Checagem estática sobre o SQL da migração 0012 (SPEC-011, ADR 049). A função é de leitura
(`INVOKER`), não grava nada e só levanta o erro de data ausente, com `ERRCODE` e `MESSAGE` literais.
"""

from __future__ import annotations

import importlib.util
import re
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[2]
ARQUIVO = RAIZ / "db" / "migrations" / "versions" / "0012_alertas.py"
RAISE_LITERAL = re.compile(
    r"RAISE EXCEPTION USING ERRCODE = '[A-Z0-9]{5}', MESSAGE = '(?:[^']|'')*';"
)
# Única lista de textos que a função pode devolver ou levantar; qualquer outro literal com
# espaço no SQL (texto novo, ou montado com valor) faz o teste falhar.
MENSAGENS = {
    "a reserva está abaixo de metade da meta",
    "a reserva está abaixo da meta",
    "informe o gasto essencial para calcular a meta da reserva",
    "a sobra do horizonte está negativa",
    "a sobra não é confiável: há cartão com dívida sem vencimento ou fechamento",
    "há ocorrências recorrentes vencidas sem vínculo a uma transação",
    "o saldo derivado da conta diverge do snapshot informado",
    "a data de hoje é obrigatória",
}


def _sql() -> str:
    spec = importlib.util.spec_from_file_location("migracao_0012", ARQUIVO)
    assert spec is not None and spec.loader is not None
    modulo = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(modulo)
    sql: str = modulo.SQL_ALERTAS
    return sql


def test_mensagens_da_0012_sao_literais() -> None:
    sql = _sql()
    assert "||" not in sql, "concatenação no SQL"
    assert "format(" not in sql.lower() and "concat" not in sql.lower()
    raises = re.findall(r"RAISE\b[^;]*;", sql)
    assert len(raises) == 1, "esperava só o RAISE de data de hoje ausente"
    assert RAISE_LITERAL.fullmatch(raises[0]), raises[0]
    sem_comentario = re.sub(r"--[^\n]*", "", sql)
    literais = {m for m in re.findall(r"'((?:[^']|'')*)'", sem_comentario) if " " in m}
    assert literais == MENSAGENS
    assert not any(ch.isdigit() for m in MENSAGENS for ch in m), "mensagem sem número"


def test_funcao_e_de_leitura_sem_escrita() -> None:
    sql = _sql().upper()
    assert "SECURITY DEFINER" not in sql
    assert "STABLE" in sql
    assert "SET SEARCH_PATH = PUBLIC, PG_TEMP" in sql
    for comando in ("INSERT ", "UPDATE ", "DELETE ", "TRUNCATE", "CREATE TABLE"):
        assert comando not in sql, comando
