"""Montagem de cenários dos alertas (SPEC-011, ADR 049) no `tst` e leitura de `alertas`."""

from __future__ import annotations

from datetime import date
from typing import Any

import psycopg

from tests.db.util_lancamento import compra, conta
from tests.db.util_r2 import novo_cartao, recorrente, usuario_com_corrente
from tests.db.util_reserva import nova_reserva, parametro
from tests.db.util_saldo import dia, novo_usuario, snapshot, transacao

COLUNAS = (
    "codigo",
    "tipo",
    "severidade",
    "detalhe",
    "mensagem",
    "nivel",
    "saldo_liquido",
    "meta",
    "falta",
    "cobertura_meses",
    "horizonte_dias",
    "data_fim",
    "sobra",
    "disponivel",
    "compromissos",
    "sobra_nao_confiavel",
    "vencidas",
    "pendencias_vencimento",
    "conta_id",
    "data_snapshot",
    "valor_snapshot",
    "saldo_derivado",
    "divergencia",
    "quantidade",
    "bolso",
    "alocacao",
    "consumo",
    "resta",
    "mes",
)
HOJE = "2026-05-10"


def alertas(conn: psycopg.Connection, uid: int, hoje: str | date = HOJE) -> list[dict[str, Any]]:
    quando = dia(hoje) if isinstance(hoje, str) else hoje
    linhas = conn.execute(
        f"SELECT {', '.join(COLUNAS)} FROM alertas(%s, %s)",  # noqa: S608
        (uid, quando),
    ).fetchall()
    return [dict(zip(COLUNAS, linha, strict=True)) for linha in linhas]


def de(lista: list[dict[str, Any]], codigo: str) -> list[dict[str, Any]]:
    """Só os alertas de um código: quem não informou o gasto essencial também recebe o CONFIG."""
    return [a for a in lista if a["codigo"] == codigo]


def chave(a: dict[str, Any]) -> tuple[str, str, str, str]:
    return a["codigo"], a["tipo"], a["severidade"], a["detalhe"]


def r2_base(
    conn: psycopg.Connection, fixo: str | None, *, cartao_sem_vencimento: bool = False
) -> int:
    """F-ALERTA-02: corrente com 5000.00, receita recorrente de 3000.00 no dia 12 e um fixo no
    dia 15 (valor `fixo`); opcionalmente um cartão com dívida de 300.00 e sem vencimento."""
    uid, corrente = usuario_com_corrente(conn, "5000.00")
    recorrente(conn, uid, "salario", "receita", "3000.00", 12, corrente, "2026-05")
    if fixo is not None:
        recorrente(conn, uid, "aluguel", "fixo", fixo, 15, corrente, "2026-05")
    if cartao_sem_vencimento:
        cartao = novo_cartao(conn, uid, 10, None)
        compra(conn, uid, cartao, "2026-04-20", "300.00", 1)
    return uid


def reserva_com_saldo(conn: psycopg.Connection, saldo: str, gasto: str | None = "4000.00") -> int:
    """F-ALERTA-01: reserva com `saldo` em 2026-01-01 e parâmetro (3 meses) desde 2026-01-01."""
    uid = novo_usuario(conn)
    nova_reserva(conn, uid, "caixinha", {"data": "2026-01-01", "valor": saldo})
    if gasto is not None:
        parametro(conn, uid, desde="2026-01-01", meses=3, gasto=gasto)
    return uid


def conta_com_snapshots(
    conn: psycopg.Connection,
    uid: int,
    nome: str,
    snapshots: list[dict[str, str]],
    transacoes: list[dict[str, str]] | None = None,
    tipo: str = "investimento",
) -> int:
    """Conta (investimento por padrão, fora do R2) com snapshots e transações diretas."""
    c = conta(conn, uid, nome, tipo)
    for s in snapshots:
        snapshot(conn, uid, c, s["data"], s["valor"])
    for t in transacoes or []:
        transacao(conn, uid, c, t["data"], t["valor"])
    return c
