"""Montagem de cenários do R2 e dos recorrentes (SPEC-010, ADR 048) no `tst`."""

from __future__ import annotations

from datetime import date
from decimal import Decimal
from typing import Any

import psycopg

from tests.db.util_lancamento import cartao, conta, linha_credito
from tests.db.util_saldo import dec, dia, novo_usuario, snapshot

COLUNAS_SITUACAO = (
    "horizonte_dias",
    "data_fim",
    "saldos_correntes",
    "receitas_pendentes",
    "disponivel",
    "fixos_pendentes",
    "faturas_proprias",
    "compromissos",
    "sobra",
    "alerta",
    "vencidas",
    "pendencias_vencimento",
)
COLUNAS_ITENS = (
    "grupo",
    "tipo",
    "recorrente_id",
    "conta_id",
    "competencia",
    "data",
    "valor",
    "bruto",
    "pago",
    "parcial",
)
COLUNAS_OCORRENCIA = (
    "recorrente_id",
    "nome",
    "tipo",
    "conta_id",
    "mes",
    "data",
    "valor_esperado",
    "valor",
    "transacao_id",
    "vinculada",
)


def usuario_com_corrente(conn: psycopg.Connection, saldo: str = "0.00") -> tuple[int, int]:
    """Usuário com uma conta corrente de saldo inicial `saldo` (snapshot em 2026-01-01)."""
    uid = novo_usuario(conn)
    c = conta(conn, uid, "corrente")
    snapshot(conn, uid, c, "2026-01-01", saldo)
    return uid, c


def novo_cartao(
    conn: psycopg.Connection,
    uid: int,
    fechamento: int,
    vencimento: int | None,
    nome: str = "cartao",
    limite: str = "50000.00",
) -> int:
    linha, _ = linha_credito(conn, uid, f"linha_{nome}", limite)
    c = cartao(conn, uid, nome, linha, fechamento, "2026-01-01")
    if vencimento is not None:
        definir_vencimento(conn, uid, c, vencimento, "2026-01-01")
    return c


def definir_vencimento(
    conn: psycopg.Connection, uid: int, conta_id: int, dia_venc: int, desde: str
) -> int:
    linha = conn.execute(
        "SELECT vencimento_gravar(%s, %s, %s, %s)", (uid, conta_id, dia_venc, dia(desde))
    ).fetchone()
    assert linha is not None
    return int(linha[0])


def definir_horizonte(conn: psycopg.Connection, uid: int, dias: int, desde: str) -> int:
    linha = conn.execute(
        "SELECT r2_parametro_gravar(%s, %s, %s)", (uid, dias, dia(desde))
    ).fetchone()
    assert linha is not None
    return int(linha[0])


def recorrente(
    conn: psycopg.Connection,
    uid: int,
    nome: str,
    tipo: str,
    valor: str,
    dia_mes: int,
    conta_id: int,
    inicio: str,
    fim: str | None = None,
    *,
    recorrente_id: int | None = None,
    versao: int | None = None,
) -> tuple[int, int]:
    """Cria ou edita; devolve (recorrente_id, versao)."""
    linha = conn.execute(
        "SELECT recorrente_id, versao FROM recorrente_gravar("
        "%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)",
        (uid, recorrente_id, versao, nome, tipo, dec(valor), dia_mes, conta_id, inicio, fim),
    ).fetchone()
    assert linha is not None
    return int(linha[0]), int(linha[1])


def excluir_recorrente(conn: psycopg.Connection, uid: int, rid: int, versao: int) -> int:
    linha = conn.execute("SELECT recorrente_excluir(%s, %s, %s)", (uid, rid, versao)).fetchone()
    assert linha is not None
    return int(linha[0])


def vincular(conn: psycopg.Connection, uid: int, rid: int, mes: str, transacao: int) -> int:
    linha = conn.execute(
        "SELECT recorrente_vincular(%s, %s, %s, %s)", (uid, rid, mes, transacao)
    ).fetchone()
    assert linha is not None
    return int(linha[0])


def desvincular(conn: psycopg.Connection, uid: int, rid: int, mes: str) -> int:
    linha = conn.execute("SELECT recorrente_desvincular(%s, %s, %s)", (uid, rid, mes)).fetchone()
    assert linha is not None
    return int(linha[0])


def situacao(conn: psycopg.Connection, uid: int, hoje: str | date) -> dict[str, Any]:
    quando = dia(hoje) if isinstance(hoje, str) else hoje
    linha = conn.execute(
        f"SELECT {', '.join(COLUNAS_SITUACAO)} FROM r2_situacao(%s, %s)",  # noqa: S608
        (uid, quando),
    ).fetchone()
    assert linha is not None
    return dict(zip(COLUNAS_SITUACAO, linha, strict=True))


def itens(conn: psycopg.Connection, uid: int, hoje: str | date) -> list[dict[str, Any]]:
    quando = dia(hoje) if isinstance(hoje, str) else hoje
    linhas = conn.execute(
        f"SELECT {', '.join(COLUNAS_ITENS)} FROM r2_itens(%s, %s)",  # noqa: S608
        (uid, quando),
    ).fetchall()
    return [dict(zip(COLUNAS_ITENS, linha, strict=True)) for linha in linhas]


def ocorrencias(conn: psycopg.Connection, uid: int, mes: str) -> list[dict[str, Any]]:
    linhas = conn.execute(
        f"SELECT {', '.join(COLUNAS_OCORRENCIA)} FROM ocorrencias_do_mes(%s, %s)",  # noqa: S608
        (uid, mes),
    ).fetchall()
    return [dict(zip(COLUNAS_OCORRENCIA, linha, strict=True)) for linha in linhas]


def vencimento(conn: psycopg.Connection, uid: int, conta_id: int, competencia: str) -> date | None:
    linha = conn.execute(
        "SELECT vencimento_fatura(%s, %s, %s)", (uid, conta_id, competencia)
    ).fetchone()
    assert linha is not None
    resultado: date | None = linha[0]
    return resultado


def d(texto: str) -> Decimal:
    return dec(texto)


def fechamento_da_fatura(
    conn: psycopg.Connection, uid: int, conta_id: int, competencia: str
) -> date | None:
    linha = conn.execute(
        "SELECT fatura_fechamento(%s, %s, %s)", (uid, conta_id, competencia)
    ).fetchone()
    assert linha is not None
    resultado: date | None = linha[0]
    return resultado
