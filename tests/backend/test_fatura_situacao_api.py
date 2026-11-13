"""Situação da fatura (aberta/fechada) pela API (SPEC-005-AC-11, ADR 043/048/050).

Valores esperados calculados à mão: cartão com fechamento dia 10; a fatura de 2026-05 fecha em
2026-05-10; aberta enquanto hoje for anterior a essa data.
"""

from __future__ import annotations

from collections.abc import Iterator

import pytest
from fastapi.testclient import TestClient

from tests.backend.conftest import Usuario, apagar_usuarios, criar_usuario, logar
from tests.backend.util_r2_api import Cenario, escrita, hoje_em

pytestmark = pytest.mark.banco


@pytest.fixture
def outro_usuario(esquema: str) -> Iterator[Usuario]:
    u = criar_usuario(esquema, "o")
    yield u
    apagar_usuarios(esquema, [u])


@pytest.mark.parametrize(
    ("hoje", "situacao"),
    [
        ("2026-05-09", "aberta"),  # véspera do fechamento
        ("2026-05-10", "fechada"),  # no dia do fechamento já fechou (ADR 043 item 1)
        ("2026-06-20", "fechada"),
    ],
)
def test_fatura_aberta_ou_fechada_pela_data(
    client: TestClient, usuario: Usuario, hoje: str, situacao: str
) -> None:
    """SPEC-005-AC-11: a API devolve a data de fechamento efetivo e a situação derivada dela;
    não existe estado "paga"."""
    c = Cenario(client, usuario)
    cartao = c.cartao(10, 20)
    with hoje_em(client, hoje):
        r = client.get(f"/api/cartoes/{cartao}/faturas/2026-05")
    assert r.status_code == 200, r.text
    corpo = r.json()
    assert (corpo["fechamento"], corpo["situacao"]) == ("2026-05-10", situacao)


def test_fatura_sem_fechamento_nao_tem_situacao(client: TestClient, usuario: Usuario) -> None:
    """SPEC-005-AC-11: sem dia de fechamento cadastrado, fechamento e situação vêm nulos."""
    c = Cenario(client, usuario)
    r = client.post(
        "/api/linhas-credito",
        json={"nome": "Linha X", "limite": "1000"},
        headers=escrita(c.csrf),
    )
    assert r.status_code == 201, r.text
    cartao = c.conta("Sem fechamento", "divida", linha_credito_id=r.json()["linha_id"])
    with hoje_em(client, "2026-05-09"):
        r = client.get(f"/api/cartoes/{cartao}/faturas/2026-05")
    assert r.status_code == 200, r.text
    assert (r.json()["fechamento"], r.json()["situacao"]) == (None, None)


def test_fatura_de_cartao_de_outro_usuario_da_404(
    client: TestClient, usuario: Usuario, outro_usuario: Usuario
) -> None:
    """INV-13: o cartão de outro usuário responde 404 (não revela que existe), com ou sem `hoje`
    injetado; o dono continua vendo a situação."""
    c = Cenario(client, usuario)
    cartao = c.cartao(10, 20)
    with hoje_em(client, "2026-05-09"):
        assert client.get(f"/api/cartoes/{cartao}/faturas/2026-05").status_code == 200
        client.cookies.clear()
        logar(client, outro_usuario)
        r = client.get(f"/api/cartoes/{cartao}/faturas/2026-05")
    assert r.status_code == 404, r.text
