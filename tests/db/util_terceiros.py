"""Chamadas às funções de pessoa, a receber e fatura da 0008 (ADR 045), como a aplicação faz."""

from __future__ import annotations

from decimal import Decimal
from typing import Any

import psycopg

from tests.db.util_saldo import dec

CAMPOS_A_RECEBER = ("divida", "repassado", "a_receber", "credito_da_pessoa")


def nova_pessoa(conn: psycopg.Connection, user_id: int, nome: str) -> int:
    return gravar_pessoa(conn, user_id, nome)[0]


def gravar_pessoa(
    conn: psycopg.Connection,
    user_id: int,
    nome: str | None,
    pessoa: int | None = None,
    versao: int | None = None,
) -> tuple[int, int]:
    """Cria ou renomeia; devolve (pessoa_id, versao)."""
    linha = conn.execute(
        "SELECT pessoa_id, versao FROM pessoa_gravar(%s, %s, %s, %s)",
        (user_id, pessoa, versao, nome),
    ).fetchone()
    assert linha is not None
    return int(linha[0]), int(linha[1])


def excluir_pessoa(conn: psycopg.Connection, user_id: int, pessoa: int, versao: int) -> int:
    linha = conn.execute("SELECT pessoa_excluir(%s, %s, %s)", (user_id, pessoa, versao)).fetchone()
    assert linha is not None
    return int(linha[0])


def a_receber(
    conn: psycopg.Connection, user_id: int, pessoa: int
) -> tuple[Decimal, Decimal, Decimal, Decimal]:
    """(divida, repassado, a_receber, credito_da_pessoa) de uma pessoa."""
    linhas = a_receber_todas(conn, user_id, pessoa)
    assert list(linhas) == [pessoa], linhas
    return linhas[pessoa]


def a_receber_todas(
    conn: psycopg.Connection, user_id: int, pessoa: int | None = None
) -> dict[int, tuple[Decimal, Decimal, Decimal, Decimal]]:
    linhas = conn.execute(
        "SELECT pessoa_id, divida, repassado, a_receber, credito_da_pessoa "
        "FROM a_receber_pessoas(%s, %s)",
        (user_id, pessoa),
    ).fetchall()
    return {int(r[0]): (r[1], r[2], r[3], r[4]) for r in linhas}


def esperado_pessoa(esperado: dict[str, Any]) -> tuple[Decimal, Decimal, Decimal, Decimal]:
    """Tupla na ordem de `CAMPOS_A_RECEBER` a partir do bloco da fixture."""
    return tuple(dec(esperado[c]) for c in CAMPOS_A_RECEBER)  # type: ignore[return-value]


def resumo_fatura(
    conn: psycopg.Connection, user_id: int, conta_id: int, competencia: str
) -> tuple[Decimal, Decimal, Decimal]:
    """(total, propria, terceiros) da fatura; confere que `fatura_total` é o mesmo total."""
    linha = conn.execute(
        "SELECT total, propria, terceiros FROM fatura_resumo(%s, %s, %s)",
        (user_id, conta_id, competencia),
    ).fetchone()
    assert linha is not None
    total = conn.execute(
        "SELECT fatura_total(%s, %s, %s)", (user_id, conta_id, competencia)
    ).fetchone()
    assert total == (linha[0],), (total, linha)
    assert linha[1] + linha[2] == linha[0], linha  # total = própria + terceiros
    return linha[0], linha[1], linha[2]


def esperado_fatura(esperado: dict[str, Any]) -> tuple[Decimal, Decimal, Decimal]:
    return dec(esperado["total"]), dec(esperado["propria"]), dec(esperado["terceiros"])


def reais(centavos: int) -> str:
    return f"{centavos // 100}.{centavos % 100:02d}"


def contar_linhas(conn: psycopg.Connection, user_id: int) -> int:
    linha = conn.execute(
        "SELECT count(*) FROM transacao_versao WHERE user_id = %s", (user_id,)
    ).fetchone()
    assert linha is not None
    return int(linha[0])
