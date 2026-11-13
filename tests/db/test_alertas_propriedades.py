"""SPEC-011 / INV-17 e INV-38: propriedades dos alertas com Hypothesis (ADR 049).

Os esperados vêm de aritmética inteira em centavos escrita no teste (meta 12000.00 e disponível
8000.00 das fixtures F-ALERTA-01 e F-ALERTA-02), não da fórmula do SQL.
"""

from __future__ import annotations

from decimal import Decimal

import psycopg
import pytest
from hypothesis import HealthCheck, given, settings
from hypothesis import strategies as st

from tests.db.util_alertas import alertas, de, r2_base, reserva_com_saldo

pytestmark = pytest.mark.banco

CONFIG = settings(
    max_examples=40, deadline=None, suppress_health_check=[HealthCheck.function_scoped_fixture]
)
META_C = 1_200_000  # 12000.00
DISPONIVEL_C = 800_000  # 5000.00 + 3000.00


def _cent(c: int) -> str:
    return str(Decimal(c).scaleb(-2).quantize(Decimal("0.01")))


@CONFIG
@given(
    saldo_c=st.one_of(st.integers(0, 2 * META_C), st.sampled_from([599_999, 600_000, 1_199_999]))
)
def test_severidade_do_r1_muda_exatamente_nos_cortes(
    conn: psycopg.Connection, saldo_c: int
) -> None:
    uid = reserva_com_saldo(conn, _cent(saldo_c))
    lista = de(alertas(conn, uid, "2026-04-01"), "R1")
    if 2 * saldo_c < META_C:
        assert [(a["tipo"], a["severidade"]) for a in lista] == [("alerta", "alta")]
    elif saldo_c < META_C:
        assert [(a["tipo"], a["severidade"]) for a in lista] == [("aviso", "media")]
    else:
        assert lista == []


@CONFIG
@given(fixo_c=st.one_of(st.integers(1, 2 * DISPONIVEL_C), st.integers(799_990, 800_010)))
def test_r2_alerta_so_com_sobra_negativa_estrita(conn: psycopg.Connection, fixo_c: int) -> None:
    uid = r2_base(conn, _cent(fixo_c))
    lista = de(alertas(conn, uid), "R2")
    if fixo_c > DISPONIVEL_C:
        assert [(a["tipo"], a["severidade"], a["detalhe"]) for a in lista] == [
            ("alerta", "alta", "sobra_negativa")
        ]
        assert lista[0]["sobra"] < 0
    else:  # inclui a sobra exatamente zero
        assert lista == []
