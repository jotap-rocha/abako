from __future__ import annotations

import os

import psycopg
import pytest

from db.alvo import VAR_URL_TST, url_psycopg, verificar_ambiente_tst, verificar_conexao_tst


@pytest.fixture(scope="session")
def url_tst() -> str:
    """URL libpq do `tst`, validada estática e dinamicamente (current_database)."""
    if not os.environ.get(VAR_URL_TST):
        pytest.fail(
            f"{VAR_URL_TST} não definida. Crie o .env (ver .env.example) "
            "e suba o contêiner (docker compose up -d)."
        )
    url = url_psycopg(verificar_ambiente_tst())
    with psycopg.connect(url) as conn:
        verificar_conexao_tst(conn)
    return url
