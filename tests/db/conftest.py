from __future__ import annotations

import os
from collections.abc import Iterator
from pathlib import Path

import psycopg
import pytest
from alembic import command
from alembic.config import Config

from db.alvo import (
    PAPEIS_RUNTIME,
    VAR_URL_TST,
    url_psycopg,
    verificar_ambiente_tst,
    verificar_conexao_papel,
    verificar_conexao_tst,
    verificar_url_papel,
)


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


def _url_papel(papel: str) -> str:
    """URL do papel de runtime, validada pelo mesmo guarda do tst (estático + servidor)."""
    var, usuario = PAPEIS_RUNTIME[papel]
    if not os.environ.get(var):
        pytest.fail(f"{var} não definida. Veja .env.example e rode scripts.criar_papeis.")
    verificar_ambiente_tst()
    verificar_url_papel(os.environ[var], var, usuario)
    url = url_psycopg(os.environ[var])
    with psycopg.connect(url) as conn:
        verificar_conexao_papel(conn, usuario)
    return url


RAIZ = Path(__file__).resolve().parents[2]


@pytest.fixture(scope="module")
def esquema(url_tst: str) -> str:
    """Garante o esquema no head (idempotente) e devolve a URL do dono do tst."""
    command.upgrade(Config(str(RAIZ / "alembic.ini")), "head")
    return url_tst


# Escopo de função e dependência de `esquema`: o CONNECT dos papéis é concedido pela
# migração, então o guarda só pode conectar depois do upgrade.
@pytest.fixture
def url_app(esquema: str) -> str:
    return _url_papel("app")


@pytest.fixture
def url_pipeline(esquema: str) -> str:
    return _url_papel("pipeline")


@pytest.fixture
def conn(esquema: str) -> Iterator[psycopg.Connection]:
    """Conexão do dono; tudo o que o teste grava é desfeito no rollback final."""
    with psycopg.connect(esquema) as c:
        yield c
        c.rollback()
