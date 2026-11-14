"""Cenários sintéticos do pipeline (F-PIPE-01/02), montados no `tst` pelo dono e commitados.

Todo nome e descrição leva o marcador `MARC_`: nenhum pode aparecer no arquivo analítico.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from datetime import date, timedelta
from decimal import Decimal
from pathlib import Path
from typing import Any

import duckdb
import psycopg

from tests.db.util_lancamento import cartao, compra, conta, lancar, linha_credito
from tests.db.util_reserva import parametro as parametro_reserva
from tests.db.util_saldo import fixture, novo_usuario, snapshot
from tests.db.util_terceiros import nova_pessoa

MARCADOR = "MARC_"
HOJE = date(2026, 2, 20)


@dataclass(frozen=True)
class Contas:
    uid: int
    corrente: int
    reserva: int | None = None
    cartao: int | None = None
    linha: int | None = None


@dataclass(frozen=True)
class Cenario:
    a: Contas
    b: Contas


def montar(url_dono: str) -> Cenario:
    """Cria os usuários A (F-PIPE-01) e B (F-PIPE-02) e commita."""
    with psycopg.connect(url_dono) as c:
        a = novo_usuario(c)
        corrente = conta(c, a, "MARC_CORRENTE")
        reserva = conta(c, a, "MARC_RESERVA", "reserva", mae=corrente)
        linha, _ = linha_credito(c, a, "MARC_LINHA", "1000.00")
        cart = cartao(c, a, "MARC_CARTAO", linha, 10, "2025-01-01")
        pessoa = nova_pessoa(c, a, "MARC_PESSOA")
        snapshot(c, a, corrente, "2026-01-01", "1000.00")
        lancar(c, a, "receita", "2026-01-05", corrente, "500.00", descricao="MARC_DESC_RECEITA")
        lancar(c, a, "debito", "2026-01-12", corrente, "200.00", descricao="MARC_DESC_DEBITO_1")
        snapshot(c, a, corrente, "2026-02-01", "1250.00")
        lancar(c, a, "debito", "2026-02-03", corrente, "100.00", descricao="MARC_DESC_DEBITO_2")
        snapshot(c, a, reserva, "2026-01-15", "2000.00")
        lancar(c, a, "rendimento", "2026-02-01", reserva, bruto="12.00", imposto="2.00")
        parametro_reserva(c, a, desde="2026-01-01", meses=3, gasto="1000.00")
        compra(c, a, cart, "2026-01-20", "300.00", 3, descricao="MARC_DESC_COMPRA")
        compra(c, a, cart, "2026-02-05", "90.00", 1, pessoa=pessoa, descricao="MARC_DESC_TERCEIRO")
        lancar(c, a, "repasse", "2026-02-12", corrente, "30.00", pessoa=pessoa)
        lancar(c, a, "transferencia", "2026-02-15", corrente, "50.00", destino=cart)
        b = novo_usuario(c)
        corrente_b = conta(c, b, "MARC_CORRENTE_B")
        snapshot(c, b, corrente_b, "2026-01-01", "777.00")
        lancar(c, b, "debito", "2026-01-20", corrente_b, "77.00", descricao="MARC_DESC_B")
        c.commit()
    return Cenario(Contas(a, corrente, reserva, cart, linha), Contas(b, corrente_b))


def apagar(url_dono: str, cenario: Cenario) -> None:
    from tests.db.util_lancamento import apagar_usuario

    for c in (cenario.a, cenario.b):
        apagar_usuario(url_dono, c.uid)


def dias_esperados(trechos: list[dict[str, str]]) -> list[tuple[date, Decimal]]:
    """Expande os trechos da fixture (de, ate, saldo) em um saldo por dia."""
    saida: list[tuple[date, Decimal]] = []
    for t in trechos:
        d, fim = date.fromisoformat(t["de"]), date.fromisoformat(t["ate"])
        while d <= fim:
            saida.append((d, Decimal(t["saldo"])))
            d += timedelta(days=1)
    return saida


def esperado(id_fixture: str) -> dict[str, Any]:
    e: dict[str, Any] = fixture(id_fixture)["esperado"]
    return e


def tabelas_do_arquivo(arquivo: Path) -> dict[str, list[tuple[Any, ...]]]:
    """Conteúdo completo e ordenado de cada tabela (só leitura)."""
    con = duckdb.connect(str(arquivo), read_only=True)
    try:
        nomes = [r[0] for r in con.execute("SHOW TABLES").fetchall()]
        return {
            n: con.execute(f"SELECT * FROM {n} ORDER BY ALL").fetchall()  # noqa: S608
            for n in sorted(nomes)
        }
    finally:
        con.close()


def sha(arquivo: Path) -> str:
    return hashlib.sha256(arquivo.read_bytes()).hexdigest()


def retrato_do_transacional(url_dono: str) -> dict[str, tuple[int, str]]:
    """(linhas, hash do conteúdo) de cada tabela do esquema public, lido pelo dono."""
    with psycopg.connect(url_dono) as c:
        tabelas = [
            r[0]
            for r in c.execute(
                "SELECT table_name FROM information_schema.tables "
                "WHERE table_schema = 'public' AND table_type = 'BASE TABLE' ORDER BY 1"
            ).fetchall()
        ]
        saida: dict[str, tuple[int, str]] = {}
        for t in tabelas:
            linha = c.execute(
                f"SELECT count(*), md5(COALESCE(string_agg(x::text, '|' ORDER BY x::text), '')) "  # noqa: S608
                f"FROM {t} x"
            ).fetchone()
            assert linha is not None
            saida[t] = (int(linha[0]), str(linha[1]))
        c.rollback()
    return saida
