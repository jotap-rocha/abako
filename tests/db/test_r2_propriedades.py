"""SPEC-010 / INV-18, INV-19, INV-31: propriedades do R2 com Hypothesis (ADR 048).

Os esperados vêm de aritmética de datas (`datetime`, `calendar`) e de centavos inteiros escritas no
teste, não da fórmula do SQL.
"""

from __future__ import annotations

import calendar
from datetime import date, timedelta
from decimal import Decimal

import psycopg
import pytest
from hypothesis import HealthCheck, given, settings
from hypothesis import strategies as st

from tests.db.util_lancamento import compra, lancar
from tests.db.util_r2 import (
    definir_horizonte,
    itens,
    novo_cartao,
    ocorrencias,
    recorrente,
    situacao,
    usuario_com_corrente,
)
from tests.db.util_terceiros import nova_pessoa

pytestmark = pytest.mark.banco

CONFIG = settings(
    max_examples=40, deadline=None, suppress_health_check=[HealthCheck.function_scoped_fixture]
)


def _reais(centavos: int) -> str:
    return f"{centavos // 100}.{centavos % 100:02d}"


def _cent(centavos: int) -> Decimal:
    return Decimal(centavos).scaleb(-2)


@CONFIG
@given(
    inicio_dias=st.integers(0, 900),
    horizonte=st.integers(1, 60),
    deslocamento=st.integers(-5, 70),
)
def test_horizonte_inclusivo_exato(
    conn: psycopg.Connection, inicio_dias: int, horizonte: int, deslocamento: int
) -> None:
    """Data em [hoje, hoje + h] pesa na sobra; antes de hoje é vencida; depois do fim, fora."""
    hoje = date(2026, 1, 1) + timedelta(days=inicio_dias)
    alvo = hoje + timedelta(days=deslocamento)
    uid, corrente = usuario_com_corrente(conn, "0.00")
    definir_horizonte(conn, uid, horizonte, "2026-01-01")
    mes = f"{alvo.year:04d}-{alvo.month:02d}"
    recorrente(conn, uid, "unico", "fixo", "10.00", alvo.day, corrente, mes, mes)
    s = situacao(conn, uid, hoje)
    grupos = [i["grupo"] for i in itens(conn, uid, hoje)]
    assert s["data_fim"] == hoje + timedelta(days=horizonte)
    if deslocamento < 0:
        assert (grupos, s["fixos_pendentes"], s["vencidas"]) == (["vencida"], Decimal("0.00"), 1)
    elif deslocamento <= horizonte:
        assert (grupos, s["fixos_pendentes"], s["vencidas"]) == (["fixo"], Decimal("10.00"), 0)
    else:
        assert (grupos, s["fixos_pendentes"], s["vencidas"]) == ([], Decimal("0.00"), 0)
    assert s["sobra"] == -s["fixos_pendentes"]


@CONFIG
@given(
    dia_mes=st.integers(29, 31),
    ano=st.integers(2026, 2034),
    mes=st.integers(1, 12),
)
def test_dia_29_a_31_usa_o_ultimo_dia_valido(
    conn: psycopg.Connection, dia_mes: int, ano: int, mes: int
) -> None:
    """A data da ocorrência é min(dia, último dia do mês), em qualquer ano (bissexto incluído)."""
    esperado = date(ano, mes, min(dia_mes, calendar.monthrange(ano, mes)[1]))
    texto = f"{ano:04d}-{mes:02d}"
    uid, corrente = usuario_com_corrente(conn)
    recorrente(conn, uid, "mensal", "fixo", "1.00", dia_mes, corrente, texto)
    [o] = ocorrencias(conn, uid, texto)
    assert o["data"] == esperado
    linha = conn.execute("SELECT data_no_mes(%s, %s)", (dia_mes, date(ano, mes, 1))).fetchone()
    assert linha == (esperado,)


@CONFIG
@given(
    saldo=st.integers(0, 10**8),
    receitas=st.lists(st.tuples(st.integers(1, 10**6), st.integers(-3, 15)), max_size=3),
    fixos=st.lists(st.tuples(st.integers(1, 10**6), st.integers(-3, 15)), max_size=3),
    fatura=st.integers(1, 10**6),
    terceiro=st.integers(0, 10**6),
    terceiro_antes=st.booleans(),
    pago=st.integers(0, 2 * 10**6),
    vencimento=st.integers(11, 28),
)
def test_sobra_e_disponivel_menos_compromissos(
    conn: psycopg.Connection,
    saldo: int,
    receitas: list[tuple[int, int]],
    fixos: list[tuple[int, int]],
    fatura: int,
    terceiro: int,
    terceiro_antes: bool,
    pago: int,
    vencimento: int,
) -> None:
    """sobra = (saldo - pago + receitas) - (fixos + fatura própria - pago alocado a ela).

    Hoje 10/05, horizonte de 10 dias (até 20/05); fechamento 10 e vencimento `vencimento` (> 10:
    a competência 2026-05 vence em maio). A fatura só pesa se vence até 20/05. A compra de
    terceiro, anterior ou posterior à própria, absorve o pago antes ou depois dela (ADR 044).
    Ocorrência antes de hoje é vencida e fica fora.
    """
    hoje = date(2026, 5, 10)
    uid, corrente = usuario_com_corrente(conn, _reais(saldo))
    cartao_id = novo_cartao(conn, uid, 10, vencimento)
    compra(conn, uid, cartao_id, "2026-04-20", _reais(fatura), 1)
    if terceiro:
        pessoa = nova_pessoa(conn, uid, "terceiro")
        data_t = "2026-04-12" if terceiro_antes else "2026-04-25"
        compra(conn, uid, cartao_id, data_t, _reais(terceiro), 1, pessoa=pessoa)
    if pago:
        lancar(conn, uid, "transferencia", "2026-05-01", corrente, _reais(pago), destino=cartao_id)
    for n, (valor, desloca) in enumerate(receitas):
        alvo = hoje + timedelta(days=desloca)
        recorrente(
            conn, uid, f"r{n}", "receita", _reais(valor), alvo.day, corrente, "2026-05", "2026-05"
        )
    for n, (valor, desloca) in enumerate(fixos):
        alvo = hoje + timedelta(days=desloca)
        recorrente(
            conn, uid, f"f{n}", "fixo", _reais(valor), alvo.day, corrente, "2026-05", "2026-05"
        )

    dentro = range(0, 11)
    receitas_in = sum(v for v, k in receitas if k in dentro)
    fixos_in = sum(v for v, k in fixos if k in dentro)
    vencidas = sum(1 for _, k in (*receitas, *fixos) if k < 0)
    # pago alocado à fatura própria: o terceiro anterior come o pago primeiro
    pago_proprio = min(max(pago - terceiro, 0), fatura) if terceiro_antes else min(pago, fatura)
    fatura_pesa = (fatura - pago_proprio) if vencimento <= 20 else 0

    esperado_disponivel = saldo - pago + receitas_in
    esperado_compromissos = fixos_in + fatura_pesa
    s = situacao(conn, uid, hoje)
    assert s["saldos_correntes"] == _cent(saldo - pago)
    assert s["receitas_pendentes"] == _cent(receitas_in)
    assert s["fixos_pendentes"] == _cent(fixos_in)
    assert s["faturas_proprias"] == _cent(fatura_pesa)
    assert s["disponivel"] == _cent(esperado_disponivel)
    assert s["compromissos"] == _cent(esperado_compromissos)
    assert s["sobra"] == _cent(esperado_disponivel - esperado_compromissos)
    assert s["alerta"] is (esperado_disponivel < esperado_compromissos)
    assert s["vencidas"] == vencidas
    assert s["pendencias_vencimento"] == 0
