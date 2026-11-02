"""SPEC-002-AC-2 (INV-13): um usuário nunca enxerga dados de outro."""

from __future__ import annotations

from collections.abc import Iterator

import psycopg
import pytest
from fastapi.testclient import TestClient

from tests.backend.conftest import Usuario, apagar_usuarios, criar_usuario, logar

pytestmark = pytest.mark.banco


@pytest.fixture
def dois_usuarios(esquema: str) -> Iterator[tuple[Usuario, Usuario, int, int]]:
    a, b = criar_usuario(esquema, "iso_a"), criar_usuario(esquema, "iso_b")
    with psycopg.connect(esquema) as conn:
        ids = []
        for u, nome in ((a, "conta de A"), (b, "conta de B")):
            linha = conn.execute(
                "INSERT INTO conta_versao (user_id, nome) VALUES (%s, %s) RETURNING conta_id",
                (u.user_id, nome),
            ).fetchone()
            assert linha is not None
            ids.append(linha[0])
    yield a, b, ids[0], ids[1]
    apagar_usuarios(esquema, [a, b])


def test_acesso_cruzado_negado(
    client: TestClient, dois_usuarios: tuple[Usuario, Usuario, int, int]
) -> None:
    a, b, conta_a, conta_b = dois_usuarios
    logar(client, a)

    assert [c["nome"] for c in client.get("/contas").json()] == ["conta de A"]
    assert client.get(f"/contas/{conta_a}").status_code == 200
    # conta de B: 404, idêntico a uma conta que não existe
    assert client.get(f"/contas/{conta_b}").status_code == 404
    assert client.get("/contas/999999999").status_code == 404
    # `user_id` na query é ignorado: quem manda é a sessão
    r = client.get(f"/contas?user_id={b.user_id}")
    assert [c["nome"] for c in r.json()] == ["conta de A"]


def test_sem_sessao_nao_ve_nada(client: TestClient) -> None:
    assert client.get("/contas").status_code == 401
    assert client.get("/contas/1").status_code == 401
