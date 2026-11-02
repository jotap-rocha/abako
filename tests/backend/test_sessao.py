"""Expiração de sessão (ADR 038): vencida não autentica e é varrida no próximo login."""

from __future__ import annotations

import psycopg
import pytest
from fastapi.testclient import TestClient

from tests.backend.conftest import Usuario, logar

pytestmark = pytest.mark.banco


def _contar(url: str, user_id: int) -> int:
    with psycopg.connect(url) as conn:
        linha = conn.execute(
            "SELECT count(*) FROM sessao WHERE user_id = %s", (user_id,)
        ).fetchone()
    assert linha is not None
    return int(linha[0])


def test_sessao_vencida_nao_autentica_e_e_varrida(
    client: TestClient, usuario: Usuario, esquema: str
) -> None:
    logar(client, usuario)
    assert client.get("/auth/eu").status_code == 200
    with psycopg.connect(esquema) as conn:
        conn.execute(
            "UPDATE sessao SET criada_em = now() - interval '2 hours', "
            "expira_em = now() - interval '1 hour' WHERE user_id = %s",
            (usuario.user_id,),
        )
    assert client.get("/auth/eu").status_code == 401
    assert _contar(esquema, usuario.user_id) == 1  # ainda lá, só não vale

    logar(client, usuario)  # novo login varre a vencida
    assert _contar(esquema, usuario.user_id) == 1
    assert client.get("/auth/eu").status_code == 200
