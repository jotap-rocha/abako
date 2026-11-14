"""Montagem de cenários do vale (VR/VA) no `tst` e leitura de `vale_situacao` (ADR 052)."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from typing import Any

import psycopg

from tests.db.util_lancamento import conta, lancar
from tests.db.util_saldo import dec, dia, novo_usuario

COLUNAS = (
    "mes",
    "mes_encerrado",
    "estado",
    "conta_vr_id",
    "credito",
    "base_trabalho",
    "inicial_trabalho",
    "inicial_pessoal",
    "ajuste_trabalho",
    "ajuste_pessoal",
    "alocacao_trabalho",
    "alocacao_pessoal",
    "consumo_trabalho",
    "consumo_pessoal",
    "resta_trabalho",
    "resta_pessoal",
    "sobra",
    "decisao_destino",
    "decisao_versao",
    "destino_padrao",
    "saldo_total",
    "receita_caixa",
    "receita_beneficio",
    "receita_total",
)
HOJE = "2025-12-15"  # depois de todos os meses das fixtures: eles ficam encerrados


@dataclass(frozen=True)
class Vale:
    uid: int
    vr: int
    va: int
    corrente: int


def parametro(
    conn: psycopg.Connection,
    uid: int,
    conta_vr: int,
    base: str = "200.00",
    desde: str = "2025-01-01",
    padrao: str = "nenhum",
) -> int:
    linha = conn.execute(
        "SELECT vale_parametro_gravar(%s, %s, %s, %s, %s)",
        (uid, conta_vr, dec(base), padrao, dia(desde)),
    ).fetchone()
    assert linha is not None
    return int(linha[0])


def novo_vale(conn: psycopg.Connection, *, base: str = "200.00", desde: str = "2025-01-01") -> Vale:
    """Usuário com corrente, VR (marcado, base e vigência dados) e VA (benefício sem bolsos)."""
    uid = novo_usuario(conn)
    corrente = conta(conn, uid, "corrente")
    vr = conta(conn, uid, "vr", "beneficio")
    va = conta(conn, uid, "va", "beneficio")
    parametro(conn, uid, vr, base, desde)
    return Vale(uid, vr, va, corrente)


def credito(conn: psycopg.Connection, uid: int, conta_id: int, data: str, valor: str) -> int:
    return lancar(conn, uid, "receita", data, conta_id, valor)[0]


def gasto(
    conn: psycopg.Connection,
    uid: int,
    conta_id: int,
    data: str,
    valor: str,
    bolso: str | None = None,
) -> tuple[int, int, bool]:
    return lancar(conn, uid, "debito", data, conta_id, valor, bolso=bolso)


def situacao(
    conn: psycopg.Connection, uid: int, mes: str, hoje: str | date = HOJE
) -> dict[str, Any]:
    quando = dia(hoje) if isinstance(hoje, str) else hoje
    linha = conn.execute(
        f"SELECT {', '.join(COLUNAS)} FROM vale_situacao(%s, %s, %s)",  # noqa: S608
        (uid, mes, quando),
    ).fetchone()
    assert linha is not None
    return dict(zip(COLUNAS, linha, strict=True))


def decidir(conn: psycopg.Connection, uid: int, mes: str, destino: str) -> int:
    linha = conn.execute("SELECT vale_decisao_gravar(%s, %s, %s)", (uid, mes, destino)).fetchone()
    assert linha is not None
    return int(linha[0])


def mes_do_vale(
    conn: psycopg.Connection,
    v: Vale,
    mes: str,
    cred: str,
    trabalho: str = "0.00",
    pessoal: str = "0.00",
) -> None:
    """Crédito no dia 5 e uma despesa por bolso (só se > 0) no dia 10 do mês `AAAA-MM`."""
    if dec(cred) > 0:
        credito(conn, v.uid, v.vr, f"{mes}-05", cred)
    if dec(trabalho) > 0:
        gasto(conn, v.uid, v.vr, f"{mes}-10", trabalho, "trabalho")
    if dec(pessoal) > 0:
        gasto(conn, v.uid, v.vr, f"{mes}-11", pessoal, "pessoal")


def alocacao(s: dict[str, Any]) -> tuple[Decimal, Decimal]:
    return s["alocacao_trabalho"], s["alocacao_pessoal"]


def resta(s: dict[str, Any]) -> tuple[Decimal, Decimal]:
    return s["resta_trabalho"], s["resta_pessoal"]


def saldo_derivado(conn: psycopg.Connection, uid: int, conta_id: int, em: str) -> Decimal:
    linha = conn.execute("SELECT saldo_derivado(%s, %s, %s)", (uid, conta_id, dia(em))).fetchone()
    assert linha is not None
    return Decimal(linha[0])
