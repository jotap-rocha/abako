"""SPEC-001-AC-1: a suíte aborta se a conexão de banco não for a de `tst`."""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

import pytest

from db.alvo import AlvoInvalido, verificar_url_tst

RAIZ = Path(__file__).resolve().parents[2]
URL_OK = "postgresql://u:p@127.0.0.1:5433/tst"


def test_url_tst_valida_passa() -> None:
    verificar_url_tst(URL_OK)
    verificar_url_tst("postgresql+psycopg://u:p@localhost:5433/tst")


@pytest.mark.parametrize(
    "url",
    [
        "postgresql://u:p@127.0.0.1:5433/prd",  # banco errado
        "postgresql://u:p@127.0.0.1:5433/postgres",
        "postgresql://u:p@127.0.0.1:5432/tst",  # porta do outro projeto
        "postgresql://u:p@db.exemplo.com:5433/tst",  # host remoto
        "postgresql://u:p@0.0.0.0:5433/tst",
        "postgresql://u:p@127.0.0.1/tst",  # sem porta explícita
        "",
    ],
)
def test_url_fora_de_tst_levanta(url: str) -> None:
    with pytest.raises(AlvoInvalido):
        verificar_url_tst(url)


def test_aborta_fora_de_tst() -> None:
    """A suíte inteira sai com erro (não só um teste) quando o alvo é `prd`."""
    env = {
        **os.environ,
        "ABAKO_DB_MIGRATE_URL_TST": "postgresql://u:p@127.0.0.1:5433/prd",
    }
    r = subprocess.run(
        [sys.executable, "-m", "pytest", "--collect-only", "-q", "tests/db/test_guarda_tst.py"],
        cwd=RAIZ,
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )
    assert r.returncode != 0
    assert "tst" in (r.stdout + r.stderr)
    assert "test_url_tst_valida_passa" not in r.stdout  # nada foi coletado


def test_aborta_se_ambiente_for_prd() -> None:
    env = {**os.environ, "ABAKO_ENV": "prd", "ABAKO_DB_MIGRATE_URL_TST": URL_OK}
    r = subprocess.run(
        [sys.executable, "-m", "pytest", "--collect-only", "-q", "tests/db/test_guarda_tst.py"],
        cwd=RAIZ,
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )
    assert r.returncode != 0
    assert "test_url_tst_valida_passa" not in r.stdout
