"""Regras de aceite do lançamento (ADR 042): tipos ainda indisponíveis, datas, valores,
isolamento por usuário e a chave de idempotência no banco (INV-13, INV-28)."""

from __future__ import annotations

from decimal import Decimal

import psycopg
import pytest

from tests.db.util_lancamento import Recusa, apagar_usuario, conta, corrida, lancar, versoes
from tests.db.util_saldo import novo_usuario, saldo

pytestmark = pytest.mark.banco


def _hoje(conn: psycopg.Connection) -> str:
    linha = conn.execute("SELECT (now() AT TIME ZONE 'America/Sao_Paulo')::date").fetchone()
    assert linha is not None
    return str(linha[0])


def test_sinal_vem_do_tipo(conn: psycopg.Connection) -> None:
    uid = novo_usuario(conn)
    c = conta(conn, uid, "corrente")
    debito, _, _ = lancar(conn, uid, "debito", "2026-02-02", c, "50.00")
    receita, _, _ = lancar(conn, uid, "receita", "2026-02-02", c, "200.00")
    assert versoes(conn, uid, debito)[0].valor == Decimal("-50.00")
    assert versoes(conn, uid, receita)[0].valor == Decimal("200.00")
    assert saldo(conn, uid, c, "2026-02-02") == Decimal("150.00")


def test_credito_e_repasse_ainda_recusados(conn: psycopg.Connection) -> None:
    uid = novo_usuario(conn)
    c = conta(conn, uid, "corrente")
    for tipo in ("credito", "repasse", "outro"):
        with Recusa(conn, "AB422"):
            lancar(conn, uid, tipo, "2026-02-02", c, "10.00")


def test_data_e_valor_fora_do_permitido(conn: psycopg.Connection) -> None:
    uid = novo_usuario(conn)
    c = conta(conn, uid, "corrente")
    hoje = _hoje(conn)
    lancar(conn, uid, "debito", hoje, c, "1.00")  # hoje vale

    amanha = str(conn.execute("SELECT %s::date + 1", (hoje,)).fetchone()[0])  # type: ignore[index]
    for data in (amanha, "1999-12-31"):
        with Recusa(conn, "AB422"):
            lancar(conn, uid, "debito", data, c, "1.00")
    for valor in ("0.00", "-1.00", "1.005", None):
        with Recusa(conn, "AB422"):
            lancar(conn, uid, "debito", "2026-02-02", c, valor)
    with Recusa(conn, "AB422"):
        lancar(conn, uid, "debito", "2026-02-02", c, "1.00", descricao="x" * 201)


def test_conta_de_outro_usuario_nao_existe(conn: psycopg.Connection) -> None:
    uid = novo_usuario(conn)
    outro = novo_usuario(conn)
    alheia = conta(conn, outro, "do outro")
    meu, v1, _ = lancar(conn, uid, "debito", "2026-02-02", conta(conn, uid, "minha"), "1.00")

    with Recusa(conn, "AB404"):
        lancar(conn, uid, "debito", "2026-02-02", alheia, "1.00")
    # O outro usuário não edita o lançamento deste, nem sabendo o id.
    with Recusa(conn, "AB404"):
        lancar(conn, outro, "debito", "2026-02-02", alheia, "9.00", transacao_id=meu, versao=v1)


def test_mesma_chave_mesmo_corpo_devolve_o_primeiro(conn: psycopg.Connection) -> None:
    uid = novo_usuario(conn)
    c = conta(conn, uid, "corrente")
    primeiro = lancar(conn, uid, "debito", "2026-02-02", c, "10.00", chave="k-1", hash_corpo="h")
    repetido = lancar(conn, uid, "debito", "2026-02-02", c, "10.00", chave="k-1", hash_corpo="h")
    assert primeiro[2] is True and repetido[2] is False
    assert primeiro[0] == repetido[0]
    assert saldo(conn, uid, c, "2026-02-02") == Decimal("-10.00")

    with Recusa(conn, "AB422"):  # mesma chave, outro corpo
        lancar(conn, uid, "debito", "2026-02-02", c, "11.00", chave="k-1", hash_corpo="h2")
    # A chave é por usuário: outro usuário pode usar a mesma.
    outro = novo_usuario(conn)
    lancar(
        conn,
        outro,
        "debito",
        "2026-02-02",
        conta(conn, outro, "c"),
        "10.00",
        chave="k-1",
        hash_corpo="h",
    )


def test_mesma_chave_em_paralelo_devolve_o_primeiro(esquema: str) -> None:
    """Nova tentativa enquanto a primeira ainda grava: espera e devolve o original (ADR 029)."""
    with psycopg.connect(esquema) as prep:
        uid = novo_usuario(prep)
        c = conta(prep, uid, "corrente")
        prep.commit()
    try:
        primeira, segunda = corrida(
            esquema,
            lambda a: lancar(
                a, uid, "debito", "2026-02-02", c, "10.00", chave="par-1", hash_corpo="h"
            ),
            lambda b: lancar(
                b, uid, "debito", "2026-02-02", c, "10.00", chave="par-1", hash_corpo="h"
            ),
        )
        assert isinstance(primeira, tuple) and isinstance(segunda, tuple)
        assert segunda == (primeira[0], 1, False)
        with psycopg.connect(esquema) as ver:
            assert saldo(ver, uid, c, "2026-02-02") == Decimal("-10.00")
    finally:
        apagar_usuario(esquema, uid)
