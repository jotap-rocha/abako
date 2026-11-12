"""SPEC-009 / INV-17 e aporte: propriedades com Hypothesis sobre as funções puras (ADR 047).

Os esperados vêm de aritmética inteira em centavos escrita no teste, não da fórmula do SQL, e das
propriedades que definem o aporte (cobre a falta; um centavo a menos não cobre).
"""

from __future__ import annotations

from decimal import Decimal

import psycopg
import pytest
from hypothesis import HealthCheck, given, settings
from hypothesis import strategies as st

pytestmark = pytest.mark.banco

CONFIG = settings(
    max_examples=80, deadline=None, suppress_health_check=[HealthCheck.function_scoped_fixture]
)


def _cent(c: int) -> Decimal:
    return Decimal(c).scaleb(-2)


@CONFIG
@given(meta_c=st.integers(min_value=2, max_value=10**11), saldo_c=st.integers(-(10**9), 10**11))
def test_nivel_muda_exatamente_em_50_e_100_por_cento(
    conn: psycopg.Connection, meta_c: int, saldo_c: int
) -> None:
    linha = conn.execute("SELECT reserva_nivel(%s, %s)", (_cent(saldo_c), _cent(meta_c))).fetchone()
    assert linha is not None
    esperado = "critica" if 2 * saldo_c < meta_c else "atencao" if saldo_c < meta_c else "saudavel"
    assert linha[0] == esperado


@CONFIG
@given(meta_c=st.integers(min_value=2, max_value=10**11))
def test_nivel_nas_bordas_exatas(conn: psycopg.Connection, meta_c: int) -> None:
    """Um centavo abaixo/acima de cada corte (50% e 100%) troca o nível."""
    meta = _cent(meta_c)

    def nivel(saldo_c: int) -> str:
        linha = conn.execute("SELECT reserva_nivel(%s, %s)", (_cent(saldo_c), meta)).fetchone()
        assert linha is not None
        return str(linha[0])

    meio_c = meta_c // 2
    if meta_c % 2 == 0:  # 50% exato em centavos
        assert nivel(meio_c - 1) == "critica"
        assert nivel(meio_c) == "atencao"
    else:  # 50% cai entre centavos: o menor saldo inteiro que alcança é meio_c + 1
        assert nivel(meio_c) == "critica"
        assert nivel(meio_c + 1) == "atencao"
    assert nivel(meta_c - 1) == "atencao"
    assert nivel(meta_c) == "saudavel"
    assert nivel(meta_c + 1) == "saudavel"


@CONFIG
@given(falta_c=st.integers(min_value=1, max_value=10**11), meses=st.integers(1, 120))
def test_aporte_cobre_a_falta_e_um_centavo_a_menos_nao(
    conn: psycopg.Connection, falta_c: int, meses: int
) -> None:
    linha = conn.execute("SELECT reserva_aporte(%s, %s)", (_cent(falta_c), meses)).fetchone()
    assert linha is not None
    aporte: Decimal = linha[0]
    assert aporte == aporte.quantize(Decimal("0.01"))
    assert aporte * meses >= _cent(falta_c)
    assert (aporte - Decimal("0.01")) * meses < _cent(falta_c)


@CONFIG
@given(falta_c=st.integers(max_value=0, min_value=-(10**9)), meses=st.integers(1, 120))
def test_aporte_zero_quando_nao_ha_falta(
    conn: psycopg.Connection, falta_c: int, meses: int
) -> None:
    linha = conn.execute("SELECT reserva_aporte(%s, %s)", (_cent(falta_c), meses)).fetchone()
    assert linha == (Decimal("0.00"),)


def test_aporte_com_meses_menor_que_um_vale_um(conn: psycopg.Connection) -> None:
    linha = conn.execute("SELECT reserva_aporte(100.00, 0), reserva_aporte(100.00, -3)").fetchone()
    assert linha == (Decimal("100.00"), Decimal("100.00"))


@CONFIG
@given(saldo_c=st.integers(0, 10**11), gasto_c=st.integers(1, 10**9))
def test_cobertura_meio_para_cima_em_inteiros(
    conn: psycopg.Connection, saldo_c: int, gasto_c: int
) -> None:
    """Centésimos = floor((2 * saldo * 100 + gasto) / (2 * gasto)), também para saldo negativo.

    Meio-para-cima: o empate -0,005 vai para 0,00.
    """
    linha = conn.execute(
        "SELECT reserva_cobertura(%s, %s)", (_cent(saldo_c), _cent(gasto_c))
    ).fetchone()
    assert linha is not None
    centesimos = (2 * saldo_c * 100 + gasto_c) // (2 * gasto_c)
    assert linha[0] == _cent(centesimos)
