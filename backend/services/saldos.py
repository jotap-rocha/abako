"""Contas, snapshots, saldos e R4. A regra de saldo vive no SQL (migração 0004); aqui só se
orquestra a chamada, sempre com o `user_id` da sessão (INV-13)."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from decimal import Decimal

import psycopg


@dataclass(frozen=True)
class SaldoConta:
    conta_id: int
    nome: str
    conta_beneficio: bool
    saldo: Decimal
    snapshot_data: date | None
    snapshot_valor: Decimal | None


@dataclass(frozen=True)
class SnapshotRegistrado:
    snapshot_id: int
    conta_id: int
    data: date
    valor: Decimal
    saldo_inicial: bool
    saldo_derivado: Decimal | None
    divergencia: Decimal | None


@dataclass(frozen=True)
class Divergencia:
    conta_id: int
    conta_nome: str
    data_snapshot: date
    valor_snapshot: Decimal
    saldo_derivado: Decimal
    divergencia: Decimal


async def hoje(conn: psycopg.AsyncConnection) -> date:
    """Data civil de hoje em America/Sao_Paulo (nunca a data UTC do servidor)."""
    cur = await conn.execute("SELECT (now() AT TIME ZONE 'America/Sao_Paulo')::date")
    linha = await cur.fetchone()
    assert linha is not None
    resultado: date = linha[0]
    return resultado


async def listar_saldos(conn: psycopg.AsyncConnection, user_id: int, em: date) -> list[SaldoConta]:
    cur = await conn.execute(
        "SELECT c.conta_id, c.nome, c.conta_beneficio, saldo_derivado(c.user_id, c.conta_id, %s), "
        "       s.data_snapshot, s.valor "
        "FROM conta_versao c "
        "LEFT JOIN LATERAL ("
        "    SELECT v.data_snapshot, v.valor FROM snapshot_vigente v "
        "    WHERE v.user_id = c.user_id AND v.conta_id = c.conta_id AND v.data_snapshot <= %s "
        "    ORDER BY v.data_snapshot DESC LIMIT 1"
        ") s ON true "
        "WHERE c.user_id = %s AND c.vigente AND NOT c.excluida "
        "ORDER BY c.conta_id",
        (em, em, user_id),
    )
    return [SaldoConta(*linha) for linha in await cur.fetchall()]


async def registrar_snapshot(
    conn: psycopg.AsyncConnection, user_id: int, conta_id: int, data: date, valor: Decimal
) -> SnapshotRegistrado | None:
    """Grava o snapshot (append-only) e devolve a divergência do R4, se houver.

    None = a conta não existe para esse usuário (a de outro usuário também não existe).
    """
    cur = await conn.execute(
        "INSERT INTO snapshot_saldo (user_id, conta_id, data_snapshot, valor) "
        "SELECT %s, %s, %s, %s "
        "WHERE EXISTS (SELECT 1 FROM conta_versao WHERE user_id = %s AND conta_id = %s "
        "              AND vigente AND NOT excluida) "
        "RETURNING id",
        (user_id, conta_id, data, valor, user_id, conta_id),
    )
    linha = await cur.fetchone()
    if linha is None:
        return None
    snapshot_id: int = linha[0]

    cur = await conn.execute(
        "SELECT count(*) FROM snapshot_vigente WHERE user_id = %s AND conta_id = %s "
        "AND data_snapshot < %s",
        (user_id, conta_id, data),
    )
    anteriores = await cur.fetchone()
    assert anteriores is not None
    cur = await conn.execute(
        "SELECT saldo_derivado, divergencia FROM r4_divergencias(%s) "
        "WHERE conta_id = %s AND data_snapshot = %s",
        (user_id, conta_id, data),
    )
    divergente = await cur.fetchone()
    return SnapshotRegistrado(
        snapshot_id=snapshot_id,
        conta_id=conta_id,
        data=data,
        valor=valor,
        saldo_inicial=anteriores[0] == 0,
        saldo_derivado=divergente[0] if divergente else None,
        divergencia=divergente[1] if divergente else None,
    )


async def listar_r4(conn: psycopg.AsyncConnection, user_id: int) -> list[Divergencia]:
    cur = await conn.execute(
        "SELECT r.conta_id, c.nome, r.data_snapshot, r.valor_snapshot, r.saldo_derivado, "
        "       r.divergencia "
        "FROM r4_divergencias(%s) r "
        "JOIN conta_versao c ON c.user_id = %s AND c.conta_id = r.conta_id "
        "AND c.vigente AND NOT c.excluida "
        "ORDER BY r.data_snapshot DESC, r.conta_id",
        (user_id, user_id),
    )
    return [Divergencia(*linha) for linha in await cur.fetchall()]
