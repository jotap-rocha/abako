"""INV-28 / SPEC-004-AC-3: repetir a criação com a mesma chave não duplica."""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from tests.backend.conftest import Usuario, logar
from tests.backend.test_lancamentos_api import criar_conta, escrita, saldo

pytestmark = pytest.mark.banco


def test_mesma_chave_nao_duplica(client: TestClient, usuario: Usuario) -> None:
    csrf = logar(client, usuario)
    c = criar_conta(client, csrf, "Corrente")
    corpo = {
        "chave": "form-abc-123",
        "tipo": "debito",
        "data": "2026-02-02",
        "valor": "50",
        "conta_id": c,
    }

    # Duplo clique / nova tentativa depois de falha de rede: a mesma chave.
    primeira = client.post("/api/lancamentos", json=corpo, headers=escrita(csrf))
    segunda = client.post("/api/lancamentos", json=corpo, headers=escrita(csrf))
    # "50" e "50.00" são o mesmo valor: o corpo canônico é igual.
    terceira = client.post(
        "/api/lancamentos", json=corpo | {"valor": "50.00"}, headers=escrita(csrf)
    )
    assert (primeira.status_code, segunda.status_code, terceira.status_code) == (201, 200, 200)
    assert primeira.json() == segunda.json() == terceira.json()
    assert len(client.get("/api/lancamentos").json()) == 1
    assert saldo(client, c, "2026-02-28") == "-50.00"


def test_mesma_chave_com_outros_dados_e_recusada(client: TestClient, usuario: Usuario) -> None:
    csrf = logar(client, usuario)
    c = criar_conta(client, csrf, "Corrente")
    corpo = {
        "chave": "form-xyz-789",
        "tipo": "debito",
        "data": "2026-02-02",
        "valor": "50",
        "conta_id": c,
    }
    assert client.post("/api/lancamentos", json=corpo, headers=escrita(csrf)).status_code == 201

    r = client.post("/api/lancamentos", json=corpo | {"valor": "51"}, headers=escrita(csrf))
    assert r.status_code == 422
    assert "chave já usada" in r.json()["detail"]
    assert [item["valor"] for item in client.get("/api/lancamentos").json()] == ["50.00"]
