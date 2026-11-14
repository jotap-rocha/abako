"""Esquema do arquivo analítico (ADR 008/054): só ids numéricos, datas e agregados.

Não existe coluna de texto livre: nenhuma descrição, nome de conta, de pessoa ou de recorrente.
`mes`, `competencia` e `nivel` são códigos curtos gerados pelo banco (AAAA-MM e enumeração).
"""

from __future__ import annotations

from collections.abc import Sequence
from typing import Any

import duckdb

VERSAO_ESQUEMA = 1
DINHEIRO = "DECIMAL(18, 2)"

TABELAS: dict[str, tuple[tuple[str, str], ...]] = {
    "saldo_diario": (
        ("user_id", "BIGINT"),
        ("conta_id", "BIGINT"),
        ("data", "DATE"),
        ("saldo", DINHEIRO),
    ),
    "gasto_mensal": (
        ("user_id", "BIGINT"),
        ("mes", "VARCHAR"),
        ("conta_id", "BIGINT"),
        ("gasto", DINHEIRO),
    ),
    "fatura_resumo": (
        ("user_id", "BIGINT"),
        ("conta_id", "BIGINT"),
        ("competencia", "VARCHAR"),
        ("total", DINHEIRO),
        ("propria", DINHEIRO),
        ("terceiros", DINHEIRO),
    ),
    "limite_linha": (
        ("user_id", "BIGINT"),
        ("linha_id", "BIGINT"),
        ("limite", DINHEIRO),
        ("usado", DINHEIRO),
        ("disponivel", DINHEIRO),
    ),
    "cobertura_reserva": (
        ("user_id", "BIGINT"),
        ("contas_reserva", "INTEGER"),
        ("saldo_liquido", DINHEIRO),
        ("imposto_acumulado", DINHEIRO),
        ("saldo_bruto", DINHEIRO),
        ("meses_meta", "INTEGER"),
        ("gasto_essencial", DINHEIRO),
        ("meta", DINHEIRO),
        ("nivel", "VARCHAR"),
        ("falta", DINHEIRO),
        ("cobertura_meses", DINHEIRO),
        ("data_alvo", "DATE"),
        ("meses_ate_alvo", "INTEGER"),
        ("alvo_vencida", "BOOLEAN"),
        ("aporte_mensal", DINHEIRO),
        ("config_pendente", "BOOLEAN"),
    ),
    "a_receber": (("user_id", "BIGINT"), ("total_a_receber", DINHEIRO)),
    "execucao": (
        ("hoje", "DATE"),
        ("versao_esquema", "INTEGER"),
        ("ambiente", "VARCHAR"),
    ),
}
# Tabelas de dados (a `execucao` é só metadado de uma linha).
TABELAS_DE_DADOS = tuple(t for t in TABELAS if t != "execucao")
COLUNAS_DE_VALOR = {
    "saldo_diario": ("saldo",),
    "gasto_mensal": ("gasto",),
    "fatura_resumo": ("total", "propria", "terceiros"),
    "limite_linha": ("limite", "usado", "disponivel"),
    "cobertura_reserva": ("saldo_liquido", "imposto_acumulado", "saldo_bruto", "meta", "falta"),
    "a_receber": ("total_a_receber",),
}
LOTE = 500


def criar(con: duckdb.DuckDBPyConnection) -> None:
    for tabela, colunas in TABELAS.items():
        definicao = ", ".join(f"{n} {t}" for n, t in colunas)
        con.execute(f"CREATE TABLE {tabela} ({definicao})")  # noqa: S608


def inserir(con: duckdb.DuckDBPyConnection, tabela: str, linhas: Sequence[Sequence[Any]]) -> int:
    """Insere em lotes de várias linhas por comando (muito mais rápido que linha a linha)."""
    n = len(TABELAS[tabela])
    marca = "(" + ", ".join("?" * n) + ")"
    for i in range(0, len(linhas), LOTE):
        lote = linhas[i : i + LOTE]
        valores = [v for linha in lote for v in linha]
        con.execute(f"INSERT INTO {tabela} VALUES " + ", ".join([marca] * len(lote)), valores)  # noqa: S608
    return len(linhas)
