"""API do cartão (SPEC-005, ADR 043): compra a crédito parcelada, fatura, limite, fechamento e
linha de crédito. Valor esperado calculado à mão; dinheiro sempre texto."""

from __future__ import annotations

from collections.abc import Iterator
from typing import Any

import pytest
from fastapi.testclient import TestClient

from tests.backend.conftest import ORIGEM, Usuario, apagar_usuarios, criar_usuario, logar

pytestmark = pytest.mark.banco


def escrita(csrf: str) -> dict[str, str]:
    return {**ORIGEM, "X-CSRF-Token": csrf}


@pytest.fixture
def outro_usuario(esquema: str) -> Iterator[Usuario]:
    u = criar_usuario(esquema, "o")
    yield u
    apagar_usuarios(esquema, [u])


def criar_linha(client: TestClient, csrf: str, nome: str = "Linha A", limite: str = "5000") -> int:
    r = client.post(
        "/api/linhas-credito", json={"nome": nome, "limite": limite}, headers=escrita(csrf)
    )
    assert r.status_code == 201, r.text
    linha_id: int = r.json()["linha_id"]
    return linha_id


def criar_conta(
    client: TestClient, csrf: str, nome: str, tipo: str = "corrente", linha: int | None = None
) -> int:
    r = client.post(
        "/api/contas",
        json={"nome": nome, "tipo": tipo, "linha_credito_id": linha},
        headers=escrita(csrf),
    )
    assert r.status_code == 201, r.text
    conta_id: int = r.json()["conta_id"]
    return conta_id


def criar_cartao(client: TestClient, csrf: str, linha: int, nome: str = "Cartão A") -> int:
    cartao = criar_conta(client, csrf, nome, "divida", linha)
    r = client.post(
        f"/api/cartoes/{cartao}/fechamentos",
        json={"dia": 10, "vigente_desde": "2026-01-01"},
        headers=escrita(csrf),
    )
    assert r.status_code == 201, r.text
    return cartao


def comprar(client: TestClient, csrf: str, cartao: int, **campos: Any) -> Any:
    corpo = {
        "chave": "compra-0001",
        "tipo": "credito",
        "data": "2026-02-05",
        "valor": "100.00",
        "parcelas": 3,
        "conta_id": cartao,
        **campos,
    }
    return client.post("/api/lancamentos", json=corpo, headers=escrita(csrf))


def saldo(client: TestClient, conta_id: int, em: str) -> str:
    r = client.get("/api/saldos", params={"em": em})
    assert r.status_code == 200, r.text
    valor: str = next(s["saldo"] for s in r.json() if s["conta_id"] == conta_id)
    return valor


def test_credito_pela_api(client: TestClient, usuario: Usuario) -> None:
    """SPEC-005-AC-9: uma parcela por mês, negativa na dívida; recusa não-cartão; idempotência;
    409 na versão desatualizada."""
    csrf = logar(client, usuario)
    cartao = criar_cartao(client, csrf, criar_linha(client, csrf))
    corrente = criar_conta(client, csrf, "Corrente")

    # Grava: 100,00 em 3 parcelas = 33,33 + 33,33 + 33,34, uma por mês (fechamento dia 10, compra
    # dia 5: a primeira cai na fatura de fevereiro).
    r = comprar(client, csrf, cartao, descricao="  geladeira ")
    assert r.status_code == 201, r.text
    compra = r.json()
    assert compra | {"transacao_id": 0} == {
        "transacao_id": 0,
        "versao": 1,
        "tipo": "credito",
        "data": "2026-02-05",
        "valor": "100.00",
        "conta_id": cartao,
        "conta_destino_id": None,
        "bruto": None,
        "imposto": None,
        "descricao": "geladeira",
        "parcelas": 3,
        "competencia": "2026-02",
        "estorno_de": None,
        "estorno_credito": None,
    }
    tid = compra["transacao_id"]
    assert saldo(client, cartao, "2026-02-28") == "-100.00"
    for competencia, total in (("2026-02", "33.33"), ("2026-03", "33.33"), ("2026-04", "33.34")):
        fatura = client.get(f"/api/cartoes/{cartao}/faturas/{competencia}").json()
        assert fatura["total"] == total, competencia
        assert [(i["parcela"], i["parcelas"], i["valor"]) for i in fatura["itens"]] == [
            (int(competencia[-1]) - 1, 3, total)
        ]
    assert client.get(f"/api/cartoes/{cartao}/faturas/2026-05").json()["itens"] == []

    # Recusa conta que não é cartão.
    r = comprar(client, csrf, corrente, chave="compra-0002")
    assert r.status_code == 422 and "cartão" in r.json()["detail"]
    assert r.headers["X-Abako-Erro"] == "AB422"

    # Repetição da mesma chave e mesmo corpo não duplica; corpo diferente com a chave: 422.
    r = comprar(client, csrf, cartao, descricao="  geladeira ")
    assert r.status_code == 200 and r.json()["transacao_id"] == tid
    assert client.get(f"/api/cartoes/{cartao}/faturas/2026-02").json()["total"] == "33.33"
    assert saldo(client, cartao, "2026-02-28") == "-100.00"
    assert comprar(client, csrf, cartao, parcelas=4).status_code == 422

    # Versão desatualizada: a edição troca 3 parcelas por 2; reenviar a versão 1 dá 409.
    editar = {
        "tipo": "credito",
        "data": "2026-02-05",
        "valor": "100.00",
        "parcelas": 2,
        "conta_id": cartao,
        "versao": 1,
    }
    r = client.put(f"/api/lancamentos/{tid}", json=editar, headers=escrita(csrf))
    assert r.status_code == 200, r.text
    assert (r.json()["versao"], r.json()["parcelas"]) == (2, 2)
    assert client.get(f"/api/cartoes/{cartao}/faturas/2026-02").json()["total"] == "50.00"
    assert client.get(f"/api/cartoes/{cartao}/faturas/2026-04").json()["total"] == "0.00"
    r = client.put(f"/api/lancamentos/{tid}", json=editar, headers=escrita(csrf))
    assert r.status_code == 409, r.text
    assert r.headers["X-Abako-Erro"] == "AB409"


def test_parcelas_so_no_credito_e_obrigatorias(client: TestClient, usuario: Usuario) -> None:
    csrf = logar(client, usuario)
    cartao = criar_cartao(client, csrf, criar_linha(client, csrf))
    corrente = criar_conta(client, csrf, "Corrente")

    r = comprar(client, csrf, cartao, parcelas=None)
    assert r.status_code == 422 and "parcelas" in r.json()["detail"]
    r = client.post(
        "/api/lancamentos",
        json={
            "chave": "debito-0001",
            "tipo": "debito",
            "data": "2026-02-05",
            "valor": "10",
            "conta_id": corrente,
            "parcelas": 2,
        },
        headers=escrita(csrf),
    )
    assert r.status_code == 422 and "parcelas" in r.json()["detail"]
    assert comprar(client, csrf, cartao, parcelas=0).status_code == 422
    assert comprar(client, csrf, cartao, parcelas=49).status_code == 422
    r = comprar(client, csrf, cartao, tipo="repasse", parcelas=None)
    assert r.status_code == 422 and "ainda não está disponível" in r.json()["detail"]
    assert client.get("/api/lancamentos").json() == []


def test_limite_da_linha_e_pagamento(client: TestClient, usuario: Usuario) -> None:
    csrf = logar(client, usuario)
    linha = criar_linha(client, csrf, limite="150.00")
    cartao = criar_cartao(client, csrf, linha)
    outro = criar_cartao(client, csrf, linha, "Cartão B")
    corrente = criar_conta(client, csrf, "Corrente")

    comprar(client, csrf, cartao, valor="100.00", parcelas=4)
    comprar(client, csrf, outro, chave="compra-0002", valor="80.00", parcelas=1)
    r = client.get(f"/api/linhas-credito/{linha}/limite")
    assert r.json() == {"limite": "150.00", "usado": "180.00", "disponivel": "-30.00"}

    # Pagar a fatura é transferir da corrente para o cartão; devolve limite.
    r = client.post(
        "/api/lancamentos",
        json={
            "chave": "pagamento-0001",
            "tipo": "transferencia",
            "data": "2026-02-20",
            "valor": "30.00",
            "conta_id": corrente,
            "conta_destino_id": cartao,
        },
        headers=escrita(csrf),
    )
    assert r.status_code == 201, r.text
    r = client.get(f"/api/linhas-credito/{linha}/limite")
    assert r.json() == {"limite": "150.00", "usado": "150.00", "disponivel": "0.00"}


def test_linha_fechamento_e_conta_de_cartao(client: TestClient, usuario: Usuario) -> None:
    csrf = logar(client, usuario)
    linha = criar_linha(client, csrf, limite="1000")
    assert client.get("/api/linhas-credito").json() == [
        {"linha_id": linha, "nome": "Linha A", "limite": "1000.00", "versao": 1}
    ]
    r = client.put(
        f"/api/linhas-credito/{linha}",
        json={"nome": "Linha A", "limite": "2000.50", "versao": 1},
        headers=escrita(csrf),
    )
    assert r.status_code == 200 and (r.json()["limite"], r.json()["versao"]) == ("2000.50", 2)
    r = client.put(
        f"/api/linhas-credito/{linha}",
        json={"nome": "Linha A", "limite": "1", "versao": 1},
        headers=escrita(csrf),
    )
    assert r.status_code == 409 and r.headers["X-Abako-Erro"] == "AB409"
    r = client.post(
        "/api/linhas-credito", json={"nome": "linha a", "limite": "1"}, headers=escrita(csrf)
    )
    assert r.status_code == 409 and r.headers["X-Abako-Erro"] == "AB410"
    r = client.post(
        "/api/linhas-credito", json={"nome": "X", "limite": "-1"}, headers=escrita(csrf)
    )
    assert r.status_code == 422

    # Cartão exige linha; criar e editar aceitam linha_credito_id.
    r = client.post(
        "/api/contas", json={"nome": "Sem linha", "tipo": "divida"}, headers=escrita(csrf)
    )
    assert r.status_code == 422 and "linha de crédito" in r.json()["detail"]
    cartao = criar_conta(client, csrf, "Cartão A", "divida", linha)
    conta = client.get(f"/api/contas/{cartao}").json()
    assert (conta["tipo"], conta["linha_credito_id"]) == ("divida", linha)
    outra = criar_linha(client, csrf, "Linha B")
    r = client.put(
        f"/api/contas/{cartao}",
        json={"nome": "Cartão A", "tipo": "divida", "linha_credito_id": outra, "versao": 1},
        headers=escrita(csrf),
    )
    assert r.status_code == 200 and r.json()["linha_credito_id"] == outra

    # Fechamento: lista do mais recente para o mais antigo; dia fora de 1..31 é 422; conta que
    # não é cartão é 404.
    for dia, desde in ((10, "2026-01-01"), (20, "2026-06-01")):
        r = client.post(
            f"/api/cartoes/{cartao}/fechamentos",
            json={"dia": dia, "vigente_desde": desde},
            headers=escrita(csrf),
        )
        assert r.status_code == 201, r.text
    assert client.get(f"/api/cartoes/{cartao}/fechamentos").json() == [
        {"dia": 20, "vigente_desde": "2026-06-01"},
        {"dia": 10, "vigente_desde": "2026-01-01"},
    ]
    r = client.post(
        f"/api/cartoes/{cartao}/fechamentos",
        json={"dia": 32, "vigente_desde": "2026-01-01"},
        headers=escrita(csrf),
    )
    assert r.status_code == 422
    corrente = criar_conta(client, csrf, "Corrente")
    assert client.get(f"/api/cartoes/{corrente}/fechamentos").status_code == 404
    assert client.get(f"/api/cartoes/{corrente}/faturas/2026-02").status_code == 404
    assert client.get(f"/api/cartoes/{cartao}/faturas/2026-13").status_code == 422


def test_isolamento_e_csrf_das_rotas_de_cartao(
    client: TestClient, usuario: Usuario, outro_usuario: Usuario
) -> None:
    csrf = logar(client, usuario)
    linha = criar_linha(client, csrf)
    cartao = criar_cartao(client, csrf, linha)
    assert comprar(client, csrf, cartao).status_code == 201

    # Sem o token CSRF, toda escrita nova é 403.
    sem_csrf = [
        ("/api/linhas-credito", {"nome": "Z", "limite": "1"}),
        (f"/api/cartoes/{cartao}/fechamentos", {"dia": 5, "vigente_desde": "2026-01-01"}),
    ]
    for url, corpo in sem_csrf:
        assert client.post(url, json=corpo, headers=ORIGEM).status_code == 403, url
    r = client.put(
        f"/api/linhas-credito/{linha}",
        json={"nome": "Z", "limite": "1", "versao": 1},
        headers=ORIGEM,
    )
    assert r.status_code == 403

    client.cookies.clear()
    csrf_outro = logar(client, outro_usuario)
    assert client.get("/api/linhas-credito").json() == []
    assert client.get(f"/api/linhas-credito/{linha}/limite").status_code == 404
    assert client.get(f"/api/cartoes/{cartao}/fechamentos").status_code == 404
    assert client.get(f"/api/cartoes/{cartao}/faturas/2026-02").status_code == 404
    r = client.post(
        f"/api/cartoes/{cartao}/fechamentos",
        json={"dia": 5, "vigente_desde": "2026-01-01"},
        headers=escrita(csrf_outro),
    )
    assert r.status_code == 404
    r = client.put(
        f"/api/linhas-credito/{linha}",
        json={"nome": "Z", "limite": "1", "versao": 1},
        headers=escrita(csrf_outro),
    )
    assert r.status_code == 404
    r = client.post(
        "/api/contas",
        json={"nome": "Cartão intruso", "tipo": "divida", "linha_credito_id": linha},
        headers=escrita(csrf_outro),
    )
    assert r.status_code == 422  # a linha de outro usuário não existe para ele
    assert comprar(client, csrf_outro, cartao, chave="compra-9999").status_code == 404
