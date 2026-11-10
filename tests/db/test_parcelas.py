"""SPEC-005-AC-1 e AC-10 (INV-02, INV-09): parcelamento da compra a crédito, edição e exclusão.

Valores esperados vêm de fixtures/numericos.yaml (F-PARC-01/02/03), calculados à mão.
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal

import psycopg
import pytest
from hypothesis import HealthCheck, given, settings
from hypothesis import strategies as st

from tests.db.util_lancamento import (
    Recusa,
    ano_atras,
    cartao,
    compra,
    excluir,
    lancar,
    linha_credito,
    parcelas_da,
    versoes,
)
from tests.db.util_saldo import dec, fixture, novo_usuario, saldo

pytestmark = pytest.mark.banco


def _cartao(conn: psycopg.Connection, fechamento: int = 10) -> tuple[int, int, int]:
    uid = novo_usuario(conn)
    linha, _ = linha_credito(conn, uid, "linha", "5000.00")
    return uid, linha, cartao(conn, uid, "cartao", linha, fechamento, "2000-01-01")


def _valores(conn: psycopg.Connection, uid: int, transacao_id: int) -> list[Decimal]:
    """Valor de cada parcela como positivo (o banco grava a dívida com sinal negativo)."""
    return [-dec(valor) for valor, _ in parcelas_da(conn, uid, transacao_id)]


def test_ultima_absorve_centavos(conn: psycopg.Connection) -> None:
    uid, _, c = _cartao(conn, 10)
    # F-PARC-01 e F-PARC-02: o esperado vem da fixture.
    for id_ in ("F-PARC-01", "F-PARC-02"):
        f = fixture(id_)
        tid, versao, criado = compra(
            conn, uid, c, "2025-01-05", f["entrada"]["compra"], f["entrada"]["parcelas"]
        )
        assert (versao, criado) == (1, True)
        assert _valores(conn, uid, tid) == [dec(p) for p in f["esperado"]["parcelas"]], id_
        assert sum(_valores(conn, uid, tid)) == dec(f["esperado"]["soma"]), id_

    # F-PARC-03: cruza o ano, à vista, divisão exata e resto de centavos.
    f3 = fixture("F-PARC-03")
    for chave in ("caso_1", "caso_2", "caso_3"):
        caso = f3["entrada"]["casos"][int(chave[-1]) - 1]
        esperado = f3["esperado"][chave]
        tid, _, _ = compra(conn, uid, c, ano_atras(caso["data"]), caso["total"], caso["parcelas"])
        assert _valores(conn, uid, tid) == [dec(p) for p in esperado["parcelas"]], chave
        assert sum(_valores(conn, uid, tid)) == dec(esperado["soma"]), chave
        assert [comp for _, comp in parcelas_da(conn, uid, tid)] == [
            ano_atras(x) for x in esperado["competencias"]
        ], chave


@settings(
    max_examples=60,
    deadline=None,
    suppress_health_check=[HealthCheck.function_scoped_fixture],
)
@given(
    centavos=st.integers(min_value=1, max_value=10**11), n=st.integers(min_value=1, max_value=48)
)
def test_propriedade_soma_e_resto_na_ultima(
    conn: psycopg.Connection, centavos: int, n: int
) -> None:
    """Para qualquer total e n de 1 a 48: soma = total e só a última foge do valor truncado."""
    if centavos < n:  # cada parcela precisa valer ao menos 0,01
        with conn.transaction(force_rollback=True):
            uid, _, c = _cartao(conn)
            with Recusa(conn, "AB422"):
                compra(conn, uid, c, "2025-01-05", f"{Decimal(centavos) / 100:.2f}", n)
        return
    total = Decimal(centavos) / 100
    with conn.transaction(force_rollback=True):
        uid, _, c = _cartao(conn)
        tid, _, _ = compra(conn, uid, c, "2025-01-05", f"{total:.2f}", n)
        valores = _valores(conn, uid, tid)
    assert len(valores) == n
    assert sum(valores) == total
    assert all(v >= Decimal("0.01") for v in valores)
    assert len(set(valores[:-1])) <= 1  # as n-1 primeiras são iguais
    base = valores[0]
    # truncado: n * base <= total < n * (base + 0,01); o resto vai todo para a última
    assert base * n <= total < (base + Decimal("0.01")) * n
    assert Decimal(0) <= valores[-1] - base <= Decimal("0.01") * (n - 1)


def test_editar_e_excluir_compra_parcelada(conn: psycopg.Connection) -> None:
    uid, linha, c = _cartao(conn, 10)
    data = "2025-11-15"  # F-PARC-03: com fechamento 10, a primeira parcela é a de 2025-12
    tid, v1, _ = compra(conn, uid, c, data, "300.00", 3, descricao="geladeira")
    assert (v1, _valores(conn, uid, tid)) == (1, [dec("100.00")] * 3)
    assert saldo(conn, uid, c, data) == dec("-300.00")  # a dívida é o total, parcelas futuras

    # Edição: nova versão da compra inteira (F-PARC-02: 1000.00 em 6 parcelas).
    _, v2, criado = compra(
        conn, uid, c, data, "1000.00", 6, transacao_id=tid, versao=v1, descricao="geladeira"
    )
    assert (v2, criado) == (2, True)
    assert _valores(conn, uid, tid) == [
        dec(p) for p in fixture("F-PARC-02")["esperado"]["parcelas"]
    ]
    historico = versoes(conn, uid, tid)
    assert [(h.versao, h.vigente) for h in historico] == [(1, False)] * 3 + [(2, True)] * 6
    # a versão anterior saiu da dívida (limite e saldo) e da fatura
    assert saldo(conn, uid, c, data) == dec("-1000.00")
    lim = conn.execute(
        "SELECT usado FROM limite_linha(%s, %s, %s)", (uid, linha, date(2025, 11, 15))
    )
    assert lim.fetchone() == (dec("1000.00"),)
    fat = conn.execute("SELECT fatura_total(%s, %s, '2026-02')", (uid, c)).fetchone()
    assert fat == (dec("166.66"),)  # 100.00 da versão 1 não conta mais

    # Versão desatualizada: 409 e nada muda.
    with Recusa(conn, "AB409"):
        compra(conn, uid, c, data, "50.00", 1, transacao_id=tid, versao=v1)
    assert len(versoes(conn, uid, tid)) == 9

    # Exclusão lógica: a compra inteira sai da fatura, do saldo e do limite; o histórico fica.
    assert excluir(conn, uid, tid, v2) == 3
    vigentes = [h for h in versoes(conn, uid, tid) if h.vigente]
    assert len(vigentes) == 6 and all(h.excluida and h.versao == 3 for h in vigentes)
    assert len(versoes(conn, uid, tid)) == 15
    assert saldo(conn, uid, c, data) == dec("0.00")
    lim = conn.execute(
        "SELECT usado FROM limite_linha(%s, %s, %s)", (uid, linha, date(2025, 11, 15))
    )
    assert lim.fetchone() == (dec("0.00"),)
    for competencia in ("2025-12", "2026-01", "2026-02", "2026-05"):
        fat = conn.execute("SELECT fatura_total(%s, %s, %s)", (uid, c, competencia)).fetchone()
        assert fat == (dec("0.00"),), competencia
    with Recusa(conn, "AB404"):
        excluir(conn, uid, tid, 3)


def test_credito_so_em_cartao_e_parcelas_validas(conn: psycopg.Connection) -> None:
    uid, _, c = _cartao(conn)
    corrente = conn.execute(
        "SELECT conta_id FROM conta_gravar(%s, NULL, NULL, 'cc', 'corrente', NULL)", (uid,)
    ).fetchone()
    assert corrente is not None
    cc = int(corrente[0])
    with Recusa(conn, "AB422"):  # conta que não é de cartão
        compra(conn, uid, cc, "2025-01-05", "10.00", 1)
    for n in (0, 49):
        with Recusa(conn, "AB422"):
            compra(conn, uid, c, "2025-01-05", "100.00", n)
    with Recusa(conn, "AB422"):  # sem parcelas
        lancar(conn, uid, "credito", "2025-01-05", c, "10.00")
    with Recusa(conn, "AB422"):  # 0,02 em 3 parcelas: alguma valeria zero
        compra(conn, uid, c, "2025-01-05", "0.02", 3)
    with Recusa(conn, "AB422"):  # parcelas só no crédito
        lancar(conn, uid, "debito", "2025-01-05", cc, "10.00", parcelas=2)
    with Recusa(conn, "AB422"):  # a conta de cartão só recebe compra e pagamento
        lancar(conn, uid, "debito", "2025-01-05", c, "10.00")
    with Recusa(conn, "AB422"):
        lancar(conn, uid, "receita", "2025-01-05", c, "10.00")
    with Recusa(conn, "AB422"):  # repasse continua recusado
        lancar(conn, uid, "repasse", "2025-01-05", c, "10.00")
    # 48 parcelas é o teto aceito
    tid, _, _ = compra(conn, uid, c, "2025-01-05", "48.00", 48)
    assert len(parcelas_da(conn, uid, tid)) == 48


def test_credito_idempotente_pela_chave(conn: psycopg.Connection) -> None:
    uid, _, c = _cartao(conn)
    t1, v1, criado1 = compra(conn, uid, c, "2025-01-05", "90.00", 3, chave="k-1", hash_corpo="h-1")
    t2, v2, criado2 = compra(conn, uid, c, "2025-01-05", "90.00", 3, chave="k-1", hash_corpo="h-1")
    assert (t2, v2, criado1, criado2) == (t1, v1, True, False)
    assert len(parcelas_da(conn, uid, t1)) == 3  # a repetição não duplicou parcelas
    with Recusa(conn, "AB422"):  # mesma chave, outro corpo
        compra(conn, uid, c, "2025-01-05", "91.00", 3, chave="k-1", hash_corpo="h-2")
