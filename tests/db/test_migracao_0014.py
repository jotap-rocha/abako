"""SPEC-014 / ADR 054: a 0014 só concede EXECUTE de leitura ao pipeline e o downgrade revoga."""

from __future__ import annotations

from pathlib import Path

import psycopg
import pytest
from alembic import command
from alembic.config import Config

pytestmark = pytest.mark.banco

RAIZ = Path(__file__).resolve().parents[2]
GASTO = "gasto_real(bigint, text)"
RESERVA = "reserva_situacao(bigint, date)"
SALDO = "saldo_derivado(bigint, bigint, date)"


def _pode(url: str, assinatura: str) -> bool:
    with psycopg.connect(url) as c:
        linha = c.execute("SELECT has_function_privilege(%s, 'EXECUTE')", (assinatura,)).fetchone()
    assert linha is not None
    return bool(linha[0])


def test_downgrade_revoga_e_upgrade_concede(esquema: str, url_pipeline: str) -> None:
    cfg = Config(str(RAIZ / "alembic.ini"))
    try:
        assert all(_pode(url_pipeline, f) for f in (GASTO, RESERVA, SALDO))
        command.downgrade(cfg, "0013")
        assert not any(_pode(url_pipeline, f) for f in (GASTO, RESERVA, SALDO))
    finally:
        command.upgrade(cfg, "head")
    assert all(_pode(url_pipeline, f) for f in (GASTO, RESERVA, SALDO))
