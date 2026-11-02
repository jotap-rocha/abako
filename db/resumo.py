"""Resumo de conferência da restauração (SPEC-001-AC-14): contagem e somas por tabela.

Só agregados (count e sum das colunas NUMERIC); nenhum valor individual é lido ou impresso.
"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal

import psycopg
from psycopg import sql


@dataclass(frozen=True)
class ResumoTabela:
    tabela: str
    linhas: int
    somas: dict[str, Decimal]


def conectar_somente_leitura(url: str) -> psycopg.Connection[tuple[object, ...]]:
    """Conexão em que nenhuma transação escreve.

    `read_only` é ajustado antes do primeiro `execute` (no psycopg 3 o primeiro comando já
    abre a transação, e um `SET SESSION ...` posterior não valeria para ela). O
    `default_transaction_read_only=on` do servidor cobre também o modo autocommit.
    """
    conn = psycopg.connect(url, options="-c default_transaction_read_only=on")
    conn.read_only = True
    return conn


def resumir(conn: psycopg.Connection[tuple[object, ...]]) -> list[ResumoTabela]:
    tabelas = [
        str(r[0])
        for r in conn.execute(
            "SELECT c.relname FROM pg_class c JOIN pg_namespace n ON n.oid = c.relnamespace "
            "WHERE n.nspname = 'public' AND c.relkind IN ('r', 'p') ORDER BY c.relname"
        ).fetchall()
    ]
    resumo: list[ResumoTabela] = []
    for tabela in tabelas:
        colunas = [
            str(r[0])
            for r in conn.execute(
                "SELECT column_name FROM information_schema.columns "
                "WHERE table_schema = 'public' AND table_name = %s AND data_type = 'numeric' "
                "ORDER BY ordinal_position",
                (tabela,),
            ).fetchall()
        ]
        exprs = [sql.SQL("count(*)")] + [
            sql.SQL("coalesce(sum({}), 0)").format(sql.Identifier(c)) for c in colunas
        ]
        consulta = sql.SQL("SELECT {} FROM {}").format(
            sql.SQL(", ").join(exprs), sql.Identifier("public", tabela)
        )
        linha = conn.execute(consulta).fetchone()
        if linha is None:  # count(*) sempre devolve uma linha; `assert` some com python -O
            raise RuntimeError(f"resumo sem linha para {tabela}")
        somas = {c: Decimal(str(v)) for c, v in zip(colunas, linha[1:], strict=True)}
        resumo.append(ResumoTabela(tabela, int(str(linha[0])), somas))
    return resumo


def formatar(resumo: list[ResumoTabela]) -> list[str]:
    linhas = []
    for r in resumo:
        somas = "".join(f"; soma({c})={v}" for c, v in r.somas.items())
        linhas.append(f"{r.tabela}: {r.linhas} linhas{somas}")
    return linhas


def banco_vazio(conn: psycopg.Connection[tuple[object, ...]]) -> bool:
    """Sem nenhuma tabela/sequência/view fora dos esquemas de sistema."""
    linha = conn.execute(
        "SELECT count(*) FROM pg_class c JOIN pg_namespace n ON n.oid = c.relnamespace "
        "WHERE n.nspname NOT IN ('pg_catalog', 'information_schema') "
        "AND n.nspname NOT LIKE 'pg_toast%' AND c.relkind IN ('r', 'p', 'S', 'v', 'm')"
    ).fetchone()
    return linha is not None and int(str(linha[0])) == 0
