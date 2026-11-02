"""SPEC-001-AC-3: as migrações Alembic aplicam e revertem em `tst` sem erro."""

from __future__ import annotations

from pathlib import Path

import psycopg
import pytest
from alembic import command
from alembic.config import Config

RAIZ = Path(__file__).resolve().parents[2]

pytestmark = pytest.mark.banco


def _cfg() -> Config:
    return Config(str(RAIZ / "alembic.ini"))


def _funcao_baseline(url: str) -> bool:
    with psycopg.connect(url) as conn:
        row = conn.execute("SELECT to_regproc('public.abako_banco_tst')").fetchone()
        return bool(row and row[0])


def test_aplica_e_reverte(url_tst: str) -> None:
    cfg = _cfg()
    command.downgrade(cfg, "base")  # parte de um tst limpo
    command.upgrade(cfg, "head")
    assert _funcao_baseline(url_tst)
    command.downgrade(cfg, "base")
    assert not _funcao_baseline(url_tst)
    command.upgrade(cfg, "head")  # reaplica do zero
    assert _funcao_baseline(url_tst)
    command.downgrade(cfg, "base")
    assert not _funcao_baseline(url_tst)
