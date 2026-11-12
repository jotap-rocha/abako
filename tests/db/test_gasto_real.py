"""SPEC-008 (INV-04, 05, 11, 20, 24; ADR 046): gasto real e receita de caixa do mês.

Esperados de F-GASTO-01..03 (fixtures/numericos.yaml), calculados à mão. As datas dos cenários
são deste arquivo ou das fixtures: fechamento no dia 10, compra até o dia 9 na competência do mês,
do dia 10 em diante na seguinte.
"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from typing import Any

import psycopg
import pytest
from hypothesis import HealthCheck, given, settings
from hypothesis import strategies as st

from tests.db.test_estorno import Cenario, estornar, montar, pagar
from tests.db.util_lancamento import Recusa, compra, conta, lancar
from tests.db.util_saldo import dec, fixture, novo_usuario, saldo
from tests.db.util_terceiros import nova_pessoa, reais, resumo_fatura

pytestmark = pytest.mark.banco

MESES_2025 = [f"2025-{m:02d}" for m in range(1, 13)]


@dataclass(frozen=True)
class Mundo:
    c: Cenario
    reserva: int
    investimento: int
    vale: int
    pessoa_b: int

    def contas(self) -> dict[str, int]:
        return {
            "corrente": self.c.corrente,
            "reserva": self.reserva,
            "investimento": self.investimento,
            "vale": self.vale,
            "cartao": self.c.cartao,
        }


def montar_mundo(conn: psycopg.Connection) -> Mundo:
    c = montar(conn)
    return Mundo(
        c,
        reserva=conta(conn, c.uid, "reserva", "reserva", mae=c.corrente),
        investimento=conta(conn, c.uid, "inv", "investimento"),
        vale=conta(conn, c.uid, "vale", "beneficio"),
        pessoa_b=nova_pessoa(conn, c.uid, "pessoa_b"),
    )


def gasto(conn: psycopg.Connection, uid: int, mes: str) -> Decimal:
    linha = conn.execute("SELECT gasto_real(%s, %s)", (uid, mes)).fetchone()
    assert linha is not None
    valor: Decimal = linha[0]
    return valor


def por_conta(conn: psycopg.Connection, uid: int, mes: str) -> dict[int, Decimal]:
    linhas = conn.execute(
        "SELECT conta_id, valor FROM gasto_real_por_conta(%s, %s)", (uid, mes)
    ).fetchall()
    return {int(r[0]): r[1] for r in linhas}


def receitas(conn: psycopg.Connection, uid: int, mes: str) -> tuple[Decimal, Decimal, Decimal]:
    """(caixa, beneficio, total) do mês."""
    linha = conn.execute(
        "SELECT receita_caixa(%s, %s), receita_beneficio(%s, %s), receita_total(%s, %s)",
        (uid, mes, uid, mes, uid, mes),
    ).fetchone()
    assert linha is not None
    return linha[0], linha[1], linha[2]


def aplicar(conn: psycopg.Connection, m: Mundo, item: dict[str, Any]) -> None:
    """Lança um item da lista `lancamentos` de F-GASTO-02."""
    contas, uid, tipo = m.contas(), m.c.uid, item["tipo"]
    if tipo in ("debito", "receita"):
        lancar(conn, uid, tipo, item["data"], contas[item["conta"]], item["valor"])
    elif tipo == "rendimento":
        lancar(
            conn, uid, tipo, item["data"], contas[item["conta"]],
            bruto=item["bruto"], imposto=item["imposto"],
        )  # fmt: skip
    elif tipo in ("transferencia", "investimento"):
        lancar(
            conn, uid, tipo, item["data"], contas[item["de"]], item["valor"],
            destino=contas[item["para"]],
        )  # fmt: skip
    elif tipo == "pagamento_fatura":  # pagar a fatura é uma transferência para o cartão
        lancar(
            conn, uid, "transferencia", item["data"], contas[item["de"]], item["valor"],
            destino=contas[item["para"]],
        )  # fmt: skip
    elif tipo == "repasse":
        lancar(
            conn, uid, tipo, item["data"], contas[item["conta"]], item["valor"], pessoa=m.pessoa_b
        )
    else:
        raise AssertionError(tipo)


def montar_f_gasto_02(conn: psycopg.Connection) -> Mundo:
    entrada = fixture("F-GASTO-02")["entrada"]
    m = montar_mundo(conn)
    for k in entrada["compras"]:
        pessoa = m.pessoa_b if k["pessoa"] == "pessoa_b" else None
        compra(conn, m.c.uid, m.c.cartao, k["data"], k["total"], k["parcelas"], pessoa=pessoa)
    for item in entrada["lancamentos"]:
        aplicar(conn, m, item)
    return m


# ---------------------------------------------------------------------------------------------
# SPEC-008-AC-1: exclui as categorias não-gasto
# ---------------------------------------------------------------------------------------------


def test_f_gasto_01(conn: psycopg.Connection) -> None:
    f = fixture("F-GASTO-01")
    m = montar_mundo(conn)
    uid, mes = m.c.uid, f["entrada"]["mes"]
    for item in f["entrada"]["itens"]:
        tipo, valor = item["tipo"], item["valor"]
        if tipo == "debito":
            alvo = m.vale if item.get("conta") == "beneficio" else m.c.corrente
            lancar(conn, uid, "debito", "2026-03-10", alvo, valor)
        elif tipo == "credito_parcela":  # compra à vista no cartão: a parcela cai em 2026-03
            pessoa = m.pessoa_b if item["pessoa"] == "pessoa_b" else None
            compra(conn, uid, m.c.cartao, "2026-03-05", valor, 1, pessoa=pessoa)
        elif tipo == "pagamento_fatura":
            pagar(conn, m.c, valor, "2026-03-20")
        elif tipo == "transferencia":
            lancar(conn, uid, tipo, "2026-03-11", m.c.corrente, valor, destino=m.reserva)
        elif tipo == "investimento":
            lancar(conn, uid, tipo, "2026-03-12", m.c.corrente, valor, destino=m.investimento)
        elif tipo == "repasse":
            lancar(conn, uid, tipo, "2026-03-13", m.c.corrente, valor, pessoa=m.pessoa_b)
        elif tipo == "rendimento":  # 12,00 bruto − 2,00 de imposto = 10,00 creditados
            lancar(conn, uid, tipo, "2026-03-14", m.reserva, bruto="12.00", imposto="2.00")
        else:
            raise AssertionError(tipo)
    assert gasto(conn, uid, mes) == dec(f["esperado"]["gasto_real"])
    # a reserva recebeu 300,00 (transferência) e 10,00 (rendimento líquido); nada disso é receita
    assert saldo(conn, uid, m.reserva, "2026-03-31") == dec("310.00")
    assert receitas(conn, uid, mes) == (dec("0.00"),) * 3


def test_rendimento_com_imposto_fica_fora(conn: psycopg.Connection) -> None:
    """INV-04: nem o rendimento nem o imposto retido entram no gasto real; não é receita."""
    m = montar_mundo(conn)
    lancar(conn, m.c.uid, "rendimento", "2025-04-15", m.reserva, bruto="10.00", imposto="2.00")
    assert saldo(conn, m.c.uid, m.reserva, "2025-04-30") == dec("8.00")  # F-REND-01: líquido
    assert gasto(conn, m.c.uid, "2025-04") == dec("0.00")
    assert receitas(conn, m.c.uid, "2025-04") == (dec("0.00"),) * 3


# ---------------------------------------------------------------------------------------------
# SPEC-008-AC-2: pagamento de fatura nunca é gasto
# ---------------------------------------------------------------------------------------------


def test_pagamento_fatura_nao_e_gasto(conn: psycopg.Connection) -> None:
    m = montar_mundo(conn)
    uid = m.c.uid
    e = fixture("F-GASTO-02")["esperado"]
    # A: 300,00 em 3x (100,00 em 03, 04 e 05)
    compra(conn, uid, m.c.cartao, "2025-03-05", "300.00", 3)
    antes = [gasto(conn, uid, mes) for mes in ("2025-03", "2025-04", "2025-05")]
    assert antes == [dec("100.00")] * 3

    pagar(conn, m.c, "150.00", "2025-04-18")  # pagamento parcial da fatura, em abril
    depois = [gasto(conn, uid, mes) for mes in ("2025-03", "2025-04", "2025-05")]
    assert depois == antes  # o pagamento não muda o gasto de mês nenhum
    # o gasto é contado nas parcelas: soma dos meses = total da compra, e não o valor pago
    assert sum(depois) == dec("300.00")
    assert resumo_fatura(conn, uid, m.c.cartao, "2025-04")[0] == dec("100.00")
    assert e["gasto_real_2025_06"] == "0.00"  # sem parcela, sem gasto (fixture F-GASTO-02)
    assert gasto(conn, uid, "2025-06") == dec(e["gasto_real_2025_06"])


# ---------------------------------------------------------------------------------------------
# SPEC-008-AC-3: terceiro fora do gasto, dentro de fatura e limite
# ---------------------------------------------------------------------------------------------


def test_terceiro_fora_do_gasto(conn: psycopg.Connection) -> None:
    m = montar_mundo(conn)
    uid = m.c.uid
    compra(conn, uid, m.c.cartao, "2025-04-05", "90.00", 1, pessoa=m.pessoa_b)  # F-GASTO-02, C
    assert gasto(conn, uid, "2025-04") == dec("0.00")
    assert por_conta(conn, uid, "2025-04") == {}
    # mas entra na fatura (terceiros) e no limite usado (INV-11)
    assert resumo_fatura(conn, uid, m.c.cartao, "2025-04") == (
        dec("90.00"), dec("0.00"), dec("90.00"),
    )  # fmt: skip
    usado = conn.execute(
        "SELECT usado FROM limite_linha(%s, %s, DATE '2025-04-05')", (uid, m.c.linha)
    ).fetchone()
    assert usado == (dec("90.00"),)
    # a compra própria ao lado entra normalmente
    compra(conn, uid, m.c.cartao, "2025-04-06", "40.00", 1)
    assert gasto(conn, uid, "2025-04") == dec("40.00")


# ---------------------------------------------------------------------------------------------
# SPEC-008-AC-4: conta de benefício fora do gasto e da receita de caixa
# ---------------------------------------------------------------------------------------------


def test_conta_de_beneficio(conn: psycopg.Connection) -> None:
    m = montar_mundo(conn)
    uid = m.c.uid
    lancar(conn, uid, "debito", "2025-04-10", m.vale, "40.00")
    lancar(conn, uid, "receita", "2025-04-05", m.vale, "400.00")
    assert gasto(conn, uid, "2025-04") == dec("0.00")
    assert por_conta(conn, uid, "2025-04") == {}
    # a receita do vale nunca entra na de caixa; a total soma as duas (INV-24)
    assert receitas(conn, uid, "2025-04") == (dec("0.00"), dec("400.00"), dec("400.00"))
    # com um débito e uma receita de caixa ao lado, só eles contam no gasto e na caixa
    lancar(conn, uid, "debito", "2025-04-11", m.c.corrente, "7.50")
    lancar(conn, uid, "receita", "2025-04-12", m.c.corrente, "100.00")
    assert gasto(conn, uid, "2025-04") == dec("7.50")
    assert receitas(conn, uid, "2025-04") == (dec("100.00"), dec("400.00"), dec("500.00"))


# ---------------------------------------------------------------------------------------------
# SPEC-008-AC-5: mês misto (parcelas de compras diferentes, reserva, rendimento, repasse...)
# ---------------------------------------------------------------------------------------------


def test_mes_misto_f_gasto_02(conn: psycopg.Connection) -> None:
    e = fixture("F-GASTO-02")["esperado"]
    m = montar_f_gasto_02(conn)
    uid = m.c.uid
    for mes in ("2025_03", "2025_04", "2025_05", "2025_06"):
        competencia = mes.replace("_", "-")
        assert gasto(conn, uid, competencia) == dec(e[f"gasto_real_{mes}"]), competencia
    # por conta em abril: débito da corrente, débito da reserva e as duas parcelas no cartão
    esperado = e["gasto_por_conta_2025_04"]
    assert por_conta(conn, uid, "2025-04") == {
        m.c.corrente: dec(esperado["corrente"]),
        m.reserva: dec(esperado["reserva"]),
        m.c.cartao: dec(esperado["cartao"]),
    }


def test_debito_em_reserva_e_investimento_conta_como_gasto(conn: psycopg.Connection) -> None:
    """ADR 046 item 5: débito é consumo onde quer que saia; só transferência e aporte não contam."""
    m = montar_mundo(conn)
    uid = m.c.uid
    lancar(conn, uid, "debito", "2025-04-09", m.reserva, "25.00")  # F-GASTO-02
    lancar(conn, uid, "debito", "2025-04-09", m.investimento, "35.00")
    lancar(conn, uid, "transferencia", "2025-04-10", m.c.corrente, "500.00", destino=m.reserva)
    lancar(conn, uid, "investimento", "2025-04-10", m.c.corrente, "700.00", destino=m.investimento)
    assert gasto(conn, uid, "2025-04") == dec("60.00")
    assert por_conta(conn, uid, "2025-04") == {
        m.reserva: dec("25.00"),
        m.investimento: dec("35.00"),
    }


def test_debito_fora_do_mes_civil_nao_conta(conn: psycopg.Connection) -> None:
    m = montar_mundo(conn)
    uid = m.c.uid
    for data in ("2025-03-31", "2025-04-01", "2025-04-30", "2025-05-01"):
        lancar(conn, uid, "debito", data, m.c.corrente, "10.00")
    assert gasto(conn, uid, "2025-04") == dec("20.00")  # só os dias 1 e 30
    assert gasto(conn, uid, "2025-03") == dec("10.00")
    assert gasto(conn, uid, "2025-05") == dec("10.00")


# ---------------------------------------------------------------------------------------------
# SPEC-008-AC-6: receita de caixa
# ---------------------------------------------------------------------------------------------


def test_receita_de_caixa_f_gasto_02(conn: psycopg.Connection) -> None:
    e = fixture("F-GASTO-02")["esperado"]
    m = montar_f_gasto_02(conn)
    # repasse, rendimento, transferência, investimento e o vale não são receita de caixa
    assert receitas(conn, m.c.uid, "2025-04") == (
        dec(e["receita_caixa_2025_04"]),
        dec(e["receita_beneficio_2025_04"]),
        dec(e["receita_total_2025_04"]),
    )
    assert receitas(conn, m.c.uid, "2025-03")[0] == dec(e["receita_caixa_2025_03"])
    assert receitas(conn, m.c.uid, "2025-06") == (dec("0.00"),) * 3


def test_receita_total_e_caixa_mais_beneficio(conn: psycopg.Connection) -> None:
    """INV-24: total = caixa + vale; a tela principal usa só a de caixa (F-VALE-05)."""
    f = fixture("F-VALE-05")
    m = montar_mundo(conn)
    lancar(conn, m.c.uid, "receita", "2025-04-02", m.c.corrente, f["entrada"]["receita_caixa"])
    lancar(conn, m.c.uid, "receita", "2025-04-05", m.vale, f["entrada"]["credito_mes"])
    caixa, beneficio, total = receitas(conn, m.c.uid, "2025-04")
    assert caixa == dec(f["esperado"]["tela_principal_mostra"])
    assert beneficio == dec("1000.00")
    assert total == dec(f["esperado"]["receita_total"])


# ---------------------------------------------------------------------------------------------
# SPEC-008-AC-7: estorno tira a compra do gasto nas competências originais
# ---------------------------------------------------------------------------------------------


def test_estorno_nas_competencias_originais_f_gasto_03(conn: psycopg.Connection) -> None:
    e = fixture("F-GASTO-03")["esperado"]
    m = montar_mundo(conn)
    c, uid = m.c, m.c.uid
    xid, xv, _ = compra(conn, uid, c.cartao, "2025-03-05", "400.00", 4)
    compra(conn, uid, c.cartao, "2025-03-06", "60.00", 1)
    lancar(conn, uid, "debito", "2025-03-15", c.corrente, "20.00")
    lancar(conn, uid, "debito", "2025-04-08", c.corrente, "30.00")
    lancar(conn, uid, "receita", "2025-04-02", c.corrente, "1000.00")
    pagar(conn, c, "150.00", "2025-04-15")

    for mes in ("03", "04", "05", "06"):
        assert gasto(conn, uid, f"2025-{mes}") == dec(
            e["antes_do_estorno"][f"gasto_real_2025_{mes}"]
        )

    r = estornar(conn, c, xid, xv, "2025-04-20")  # parte já paga: gera crédito P na fatura
    assert r.credito > 0

    # a compra sai do gasto em TODAS as competências originais, inclusive março (já fechada)
    for mes in ("03", "04", "05", "06"):
        assert gasto(conn, uid, f"2025-{mes}") == dec(
            e["depois_do_estorno"][f"gasto_real_2025_{mes}"]
        )
    # o crédito do estorno não é receita nem gasto negativo
    assert receitas(conn, uid, "2025-04")[0] == dec(e["depois_do_estorno"]["receita_caixa_2025_04"])
    assert receitas(conn, uid, "2025-05") == (dec("0.00"),) * 3
    assert gasto(conn, uid, "2025-05") == dec("0.00")


_CONFIG = settings(
    max_examples=25, deadline=None, suppress_health_check=[HealthCheck.function_scoped_fixture]
)

_DEBITO = st.tuples(
    st.integers(min_value=0, max_value=270),  # dia a partir de 2025-01-01
    st.integers(min_value=1, max_value=100_000),  # centavos
    st.sampled_from(["corrente", "reserva", "vale"]),
)
_COMPRA = st.tuples(
    st.integers(min_value=0, max_value=270),
    st.integers(min_value=3, max_value=300_000),
    st.integers(min_value=1, max_value=3),
    st.booleans(),  # de terceiro
)


def _data(offset: int) -> str:
    # 2025-01-01 + offset, sem importar datetime no módulo: a conta é feita no banco
    return f"2025-{(offset // 30) % 9 + 1:02d}-{offset % 28 + 1:02d}"


def _soma_gasto_ano(conn: psycopg.Connection, uid: int) -> Decimal:
    linha = conn.execute(
        "SELECT sum(gasto_real(%s, m)) FROM unnest(%s::text[]) AS m", (uid, MESES_2025)
    ).fetchone()
    assert linha is not None
    soma: Decimal = linha[0]
    return soma


@_CONFIG
@given(debitos=st.lists(_DEBITO, max_size=4), compras=st.lists(_COMPRA, max_size=3))
def test_gasto_real_soma_so_saidas_proprias(
    conn: psycopg.Connection,
    debitos: list[tuple[int, int, str]],
    compras: list[tuple[int, int, int, bool]],
) -> None:
    """Soma do ano = débitos que não são do vale + totais das compras próprias (soma das parcelas
    = total, INV-02) e nunca passa do total de saídas; terceiro e vale não entram."""
    with conn.transaction(force_rollback=True):
        m = montar_mundo(conn)
        contas = {"corrente": m.c.corrente, "reserva": m.reserva, "vale": m.vale}
        for offset, centavos, onde in debitos:
            lancar(conn, m.c.uid, "debito", _data(offset), contas[onde], reais(centavos))
        for offset, centavos, n, terceiro in compras:
            compra(
                conn, m.c.uid, m.c.cartao, _data(offset), reais(centavos), n,
                pessoa=m.pessoa_b if terceiro else None,
            )  # fmt: skip
        proprio = sum(c for _, c, onde in debitos if onde != "vale") + sum(
            c for _, c, _, terceiro in compras if not terceiro
        )
        todas = sum(c for _, c, _ in debitos) + sum(c for _, c, _, _ in compras)
        total = _soma_gasto_ano(conn, m.c.uid)
        assert total == dec(reais(proprio))
        assert total <= dec(reais(todas))
        assert all(gasto(conn, m.c.uid, mes) >= 0 for mes in MESES_2025)


@_CONFIG
@given(total=st.integers(min_value=3, max_value=500_000), parcelas=st.integers(1, 3))
def test_estorno_integral_zera_o_gasto_da_compra(
    conn: psycopg.Connection, total: int, parcelas: int
) -> None:
    """Estorno sem nada pago: a compra some do gasto em todos os meses; o débito ao lado fica."""
    with conn.transaction(force_rollback=True):
        m = montar_mundo(conn)
        uid = m.c.uid
        tid, versao, _ = compra(conn, uid, m.c.cartao, "2025-03-05", reais(total), parcelas)
        lancar(conn, uid, "debito", "2025-04-08", m.c.corrente, "30.00")
        assert _soma_gasto_ano(conn, uid) == dec(reais(total)) + dec("30.00")
        estornar(conn, m.c, tid, versao, "2025-04-20")
        assert _soma_gasto_ano(conn, uid) == dec("30.00")
        assert gasto(conn, uid, "2025-04") == dec("30.00")
        assert receitas(conn, uid, "2025-04") == (dec("0.00"),) * 3


# ---------------------------------------------------------------------------------------------
# SPEC-008-AC-8: isolamento por user_id
# ---------------------------------------------------------------------------------------------


def test_leituras_com_user_id_de_outro_usuario_devolvem_zero(conn: psycopg.Connection) -> None:
    m = montar_f_gasto_02(conn)
    outro = novo_usuario(conn)
    for mes in ("2025-03", "2025-04", "2025-05"):
        assert gasto(conn, outro, mes) == dec("0.00")
        assert por_conta(conn, outro, mes) == {}
        assert receitas(conn, outro, mes) == (dec("0.00"),) * 3
        n = conn.execute("SELECT count(*) FROM gasto_real_itens(%s, %s)", (outro, mes)).fetchone()
        assert n == (0,)
    # o dono continua vendo os próprios valores
    assert gasto(conn, m.c.uid, "2025-04") == dec("285.00")
    # e o outro usuário, com lançamento próprio, vê só o dele
    corrente_outro = conta(conn, outro, "corrente")
    lancar(conn, outro, "debito", "2025-04-08", corrente_outro, "5.00")
    assert gasto(conn, outro, "2025-04") == dec("5.00")
    assert gasto(conn, m.c.uid, "2025-04") == dec("285.00")


# ---------------------------------------------------------------------------------------------
# SPEC-008-AC-9: leitura pura, mês inválido recusado
# ---------------------------------------------------------------------------------------------


def test_leituras_nao_gravam_e_recusam_mes_invalido(conn: psycopg.Connection) -> None:
    m = montar_f_gasto_02(conn)
    uid = m.c.uid

    def contagem() -> tuple[object, ...]:
        linha = conn.execute(
            "SELECT (SELECT count(*) FROM transacao_versao), (SELECT count(*) FROM conta_versao), "
            "(SELECT count(*) FROM pessoa)"
        ).fetchone()
        assert linha is not None
        return tuple(linha)

    antes = contagem()
    gasto(conn, uid, "2025-04")
    receitas(conn, uid, "2025-04")
    por_conta(conn, uid, "2025-04")
    assert contagem() == antes

    for ruim in ("2025-4", "2025-13", "2025-00", "abril", "", " 2025-04", "2025-04-01", None):
        for consulta in (
            "SELECT gasto_real(%s, %s)",
            "SELECT * FROM gasto_real_por_conta(%s, %s)",
            "SELECT receita_caixa(%s, %s)",
            "SELECT receita_total(%s, %s)",
        ):
            with Recusa(conn, "AB422"):
                conn.execute(consulta, (uid, ruim))
    # dinheiro volta como NUMERIC (nunca float), com 2 casas
    linha = conn.execute("SELECT pg_typeof(gasto_real(%s, '2025-04'))::text", (uid,)).fetchone()
    assert linha == ("numeric",)
