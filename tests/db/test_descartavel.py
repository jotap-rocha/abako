"""Banco descartável `restauracao` (ADR 032/037): estado deixado por `scripts.criar_descartavel`
ou pelo `initdb/02-restauracao.sh`.

Conecta só como o dono do descartável (sem senha de admin). No CI, o passo de admin roda o
`criar_descartavel` duas vezes antes do check (a segunda prova a idempotência); localmente,
confere o banco que o usuário criou.
"""

from __future__ import annotations

import os
from collections.abc import Iterator

import psycopg
import pytest

from db.alvo import (
    BANCO_RESTAURACAO,
    USUARIO_RESTAURACAO,
    VAR_URL_RESTAURACAO,
    carregar_env,
    url_psycopg,
    verificar_banco_conectado,
    verificar_url_restauracao,
)
from db.resumo import banco_vazio


@pytest.fixture
def url_restauracao() -> str:
    carregar_env()
    url = os.environ.get(VAR_URL_RESTAURACAO, "")
    if not url:
        pytest.fail(
            f"{VAR_URL_RESTAURACAO} não definida (ver .env.example e scripts.criar_descartavel)"
        )
    verificar_url_restauracao(url)
    return url_psycopg(url)


@pytest.fixture
def conn_restauracao(url_restauracao: str) -> Iterator[psycopg.Connection[tuple[object, ...]]]:
    with psycopg.connect(url_restauracao) as c:
        linha = c.execute("SELECT current_database()").fetchone()
        verificar_banco_conectado(BANCO_RESTAURACAO, linha[0] if linha else None)
        yield c
        c.rollback()


@pytest.mark.banco
def test_descartavel_tem_dono_certo_e_privilegio_minimo(
    conn_restauracao: psycopg.Connection[tuple[object, ...]],
) -> None:
    linha = conn_restauracao.execute(
        "SELECT current_user, r.rolsuper, r.rolcreatedb, r.rolcreaterole, "
        "pg_get_userbyid(d.datdba), "
        "has_database_privilege('public', d.datname, 'CONNECT'), "
        "has_database_privilege('public', d.datname, 'TEMP') "
        "FROM pg_roles r, pg_database d "
        "WHERE r.rolname = current_user AND d.datname = current_database()"
    ).fetchone()
    assert linha == (USUARIO_RESTAURACAO, False, False, False, USUARIO_RESTAURACAO, False, False)


@pytest.mark.banco
def test_banco_vazio_reconhece_banco_sem_objetos(url_restauracao: str) -> None:
    # O banco de manutenção `postgres` do contêiner dedicado não tem objetos de usuário:
    # serve de caso "vazio" sem depender do estado do descartável (que pode ter uma
    # restauração do usuário). O ramo "não vazio" está em test_resumo.py.
    with psycopg.connect(url_restauracao, dbname="postgres") as c:
        assert banco_vazio(c) is True, (
            "o banco `postgres` do contêiner ganhou objetos de usuário; este teste o usa como "
            "caso vazio de referência (não é falha do guarda de restauração)"
        )
