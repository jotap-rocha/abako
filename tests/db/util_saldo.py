"""Montagem de cenários de saldo no `tst` (dono do banco) e leitura das fixtures numéricas."""

from __future__ import annotations

import uuid
from datetime import date
from decimal import Decimal
from pathlib import Path
from typing import Any

import psycopg
import yaml

FIXTURES = Path(__file__).resolve().parents[2] / "fixtures" / "numericos.yaml"


def fixture(id_: str) -> dict[str, Any]:
    dados = yaml.safe_load(FIXTURES.read_text(encoding="utf-8"))
    for f in dados["fixtures"]:
        if f["id"] == id_:
            achada: dict[str, Any] = f
            return achada
    raise KeyError(id_)


def dia(texto: str) -> date:
    return date.fromisoformat(texto)


def dec(texto: str) -> Decimal:
    return Decimal(texto)


def novo_usuario(conn: psycopg.Connection) -> int:
    linha = conn.execute(
        "INSERT INTO usuario (login) VALUES (%s) RETURNING user_id", (f"s_{uuid.uuid4().hex[:10]}",)
    ).fetchone()
    assert linha is not None
    return int(linha[0])


def nova_conta(conn: psycopg.Connection, user_id: int, nome: str = "conta") -> int:
    linha = conn.execute(
        "INSERT INTO conta_versao (user_id, nome) VALUES (%s, %s) RETURNING conta_id",
        (user_id, nome),
    ).fetchone()
    assert linha is not None
    return int(linha[0])


def snapshot(conn: psycopg.Connection, user_id: int, conta_id: int, data: str, valor: str) -> None:
    conn.execute(
        "INSERT INTO snapshot_saldo (user_id, conta_id, data_snapshot, valor) "
        "VALUES (%s, %s, %s, %s)",
        (user_id, conta_id, dia(data), dec(valor)),
    )


def transacao(
    conn: psycopg.Connection,
    user_id: int,
    conta_id: int,
    data: str,
    valor: str,
    *,
    transacao_id: int | None = None,
    versao: int = 1,
    vigente: bool = True,
    excluida: bool = False,
) -> int:
    """Insere uma versão de transação e devolve o `transacao_id` (lógico)."""
    if transacao_id is None:
        linha = conn.execute("SELECT nextval('transacao_id_seq')").fetchone()
        assert linha is not None
        transacao_id = int(linha[0])
    conn.execute(
        "INSERT INTO transacao_versao "
        "(user_id, transacao_id, versao, vigente, excluida, conta_id, data_transacao, valor, "
        " tipo) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)",
        (
            user_id,
            transacao_id,
            versao,
            vigente,
            excluida,
            conta_id,
            dia(data),
            dec(valor),
            # Cenário de saldo só precisa do sinal: saída = débito, entrada = receita.
            "debito" if dec(valor) < 0 else "receita",
        ),
    )
    return transacao_id


def editar(
    conn: psycopg.Connection, user_id: int, conta_id: int, transacao_id: int, data: str, valor: str
) -> None:
    """Edição como o ledger faz: a versão vigente deixa de ser vigente e entra a nova."""
    linha = conn.execute(
        "UPDATE transacao_versao SET vigente = false "
        "WHERE user_id = %s AND transacao_id = %s AND vigente RETURNING versao",
        (user_id, transacao_id),
    ).fetchone()
    assert linha is not None
    transacao(conn, user_id, conta_id, data, valor, transacao_id=transacao_id, versao=linha[0] + 1)


def saldo(conn: psycopg.Connection, user_id: int, conta_id: int, em: str) -> Decimal:
    linha = conn.execute(
        "SELECT saldo_derivado(%s, %s, %s)", (user_id, conta_id, dia(em))
    ).fetchone()
    assert linha is not None
    resultado: Decimal = linha[0]
    return resultado


def r4(conn: psycopg.Connection, user_id: int) -> list[tuple[int, date, Decimal, Decimal, Decimal]]:
    linhas = conn.execute(
        "SELECT conta_id, data_snapshot, valor_snapshot, saldo_derivado, divergencia "
        "FROM r4_divergencias(%s)",
        (user_id,),
    ).fetchall()
    return [(r[0], r[1], r[2], r[3], r[4]) for r in linhas]
