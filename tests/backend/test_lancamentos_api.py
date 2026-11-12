"""API de lançamentos e de edição de conta (SPEC-004, ADR 042): valor positivo como texto,
sinal pelo tipo, erros de regra traduzidos, isolamento por usuário e CSRF."""

from __future__ import annotations

from collections.abc import Iterator
from typing import Any

import pytest
from fastapi.testclient import TestClient

from tests.backend.conftest import ORIGEM, Usuario, apagar_usuarios, criar_usuario, logar

pytestmark = pytest.mark.banco

_contador = iter(range(10**9))


def escrita(csrf: str) -> dict[str, str]:
    return {**ORIGEM, "X-CSRF-Token": csrf}


def criar_conta(
    client: TestClient, csrf: str, nome: str, tipo: str = "corrente", mae: int | None = None
) -> int:
    r = client.post(
        "/api/contas",
        json={
            "nome": nome,
            "tipo": tipo,
            "conta_beneficio": tipo == "beneficio",
            "conta_mae_id": mae,
        },
        headers=escrita(csrf),
    )
    assert r.status_code == 201, r.text
    conta_id: int = r.json()["conta_id"]
    return conta_id


def lancar(client: TestClient, csrf: str, **campos: Any) -> Any:
    corpo = {"chave": f"chave-{next(_contador):08d}", **campos}
    return client.post("/api/lancamentos", json=corpo, headers=escrita(csrf))


def saldo(client: TestClient, conta_id: int, em: str) -> str:
    r = client.get("/api/saldos", params={"em": em})
    assert r.status_code == 200, r.text
    valor: str = next(s["saldo"] for s in r.json() if s["conta_id"] == conta_id)
    return valor


@pytest.fixture
def outro_usuario(esquema: str) -> Iterator[Usuario]:
    u = criar_usuario(esquema, "o")
    yield u
    apagar_usuarios(esquema, [u])


def test_ciclo_de_vida_de_um_lancamento(client: TestClient, usuario: Usuario) -> None:
    csrf = logar(client, usuario)
    c = criar_conta(client, csrf, "Corrente")

    r = lancar(
        client,
        csrf,
        tipo="debito",
        data="2026-02-02",
        valor="80",
        conta_id=c,
        descricao="  mercado  ",
    )
    assert r.status_code == 201, r.text
    criado = r.json()
    assert criado | {"transacao_id": 0} == {
        "transacao_id": 0,
        "versao": 1,
        "tipo": "debito",
        "data": "2026-02-02",
        "valor": "80.00",
        "conta_id": c,
        "conta_destino_id": None,
        "bruto": None,
        "imposto": None,
        "descricao": "mercado",
        "parcelas": None,
        "competencia": None,
        "estorno_de": None,
        "estorno_credito": None,
    }
    tid = criado["transacao_id"]
    assert saldo(client, c, "2026-02-28") == "-80.00"

    r = client.put(
        f"/api/lancamentos/{tid}",
        json={"tipo": "debito", "data": "2026-02-02", "valor": "60.00", "conta_id": c, "versao": 1},
        headers=escrita(csrf),
    )
    assert r.status_code == 200, r.text
    assert (r.json()["versao"], r.json()["valor"]) == (2, "60.00")
    assert client.get(f"/api/lancamentos/{tid}").json()["valor"] == "60.00"
    assert saldo(client, c, "2026-02-28") == "-60.00"

    r = client.delete(f"/api/lancamentos/{tid}", params={"versao": 2}, headers=escrita(csrf))
    assert r.status_code == 204, r.text
    assert client.get(f"/api/lancamentos/{tid}").status_code == 404
    assert client.get("/api/lancamentos").json() == []
    assert saldo(client, c, "2026-02-28") == "0.00"


def test_transferencia_rendimento_e_lista(client: TestClient, usuario: Usuario) -> None:
    csrf = logar(client, usuario)
    banco = criar_conta(client, csrf, "Banco")
    caixinha = criar_conta(client, csrf, "Banco Caixinha", "reserva", mae=banco)

    r = lancar(
        client,
        csrf,
        tipo="transferencia",
        data="2026-03-01",
        valor="300.00",
        conta_id=banco,
        conta_destino_id=caixinha,
    )
    assert r.status_code == 201, r.text
    assert (r.json()["valor"], r.json()["conta_destino_id"]) == ("300.00", caixinha)
    r = lancar(
        client,
        csrf,
        tipo="rendimento",
        data="2026-03-10",
        bruto="100.00",
        imposto="22.50",
        conta_id=caixinha,
    )
    assert r.status_code == 201, r.text
    assert (r.json()["valor"], r.json()["bruto"], r.json()["imposto"]) == (
        "77.50",
        "100.00",
        "22.50",
    )
    assert saldo(client, banco, "2026-03-31") == "-300.00"
    assert saldo(client, caixinha, "2026-03-31") == "377.50"

    # A lista da caixinha mostra a transferência (como destino) e o rendimento.
    lista = client.get("/api/lancamentos", params={"conta_id": caixinha}).json()
    assert [item["tipo"] for item in lista] == ["rendimento", "transferencia"]
    assert client.get("/api/lancamentos", params={"de": "2026-03-05"}).json()[0]["tipo"] == (
        "rendimento"
    )
    saldos = {s["conta_id"]: s for s in client.get("/api/saldos").json()}
    assert (saldos[caixinha]["tipo"], saldos[caixinha]["conta_mae_id"]) == ("reserva", banco)


def test_regras_viram_422_com_mensagem(client: TestClient, usuario: Usuario) -> None:
    csrf = logar(client, usuario)
    c = criar_conta(client, csrf, "Corrente")
    casos: list[tuple[dict[str, Any], str]] = [
        # crédito (SPEC-005): exige parcelas e conta de cartão; parcelas só no crédito
        ({"tipo": "credito", "valor": "10"}, "número de parcelas"),
        ({"tipo": "credito", "valor": "10", "parcelas": 2}, "só em conta de cartão"),
        ({"tipo": "debito", "valor": "10", "parcelas": 2}, "só da compra a crédito"),
        ({"tipo": "repasse", "valor": "10"}, "ainda não está disponível"),
        ({"tipo": "debito", "valor": "10", "data": "2999-01-01"}, "entre 2000 e hoje"),
        ({"tipo": "transferencia", "valor": "10", "conta_destino_id": c}, "contas diferentes"),
        ({"tipo": "rendimento", "bruto": "1.00", "imposto": "2.00"}, "bruto > 0"),
    ]
    for campos, trecho in casos:
        r = lancar(client, csrf, **({"data": "2026-02-02", "conta_id": c} | campos))
        assert r.status_code == 422, (campos, r.text)
        assert trecho in r.json()["detail"], (campos, r.text)
    # Formato inválido é barrado antes do banco (Pydantic): valor negativo ou número JSON.
    for valor in ("-10", 10):
        r = lancar(client, csrf, tipo="debito", data="2026-02-02", conta_id=c, valor=valor)
        assert r.status_code == 422, r.text
    assert client.get("/api/lancamentos").json() == []


def test_isolamento_e_csrf(
    client: TestClient, usuario: Usuario, outro_usuario: Usuario, esquema: str
) -> None:
    csrf = logar(client, usuario)
    c = criar_conta(client, csrf, "Corrente")
    tid = lancar(client, csrf, tipo="receita", data="2026-02-02", valor="10", conta_id=c).json()[
        "transacao_id"
    ]
    r = client.post(
        "/api/lancamentos",
        json={
            "chave": "sem-csrf-01",
            "tipo": "receita",
            "data": "2026-02-02",
            "valor": "1",
            "conta_id": c,
        },
        headers=ORIGEM,
    )
    assert r.status_code == 403

    client.cookies.clear()
    csrf_outro = logar(client, outro_usuario)
    assert client.get(f"/api/lancamentos/{tid}").status_code == 404
    assert client.get("/api/lancamentos").json() == []
    r = client.put(
        f"/api/lancamentos/{tid}",
        json={"tipo": "receita", "data": "2026-02-02", "valor": "99", "conta_id": c, "versao": 1},
        headers=escrita(csrf_outro),
    )
    assert r.status_code == 404, r.text  # a conta e o lançamento não existem para ele
    r = client.delete(f"/api/lancamentos/{tid}", params={"versao": 1}, headers=escrita(csrf_outro))
    assert r.status_code == 404


def test_editar_conta(client: TestClient, usuario: Usuario) -> None:
    csrf = logar(client, usuario)
    banco = criar_conta(client, csrf, "Banco")
    caixinha = criar_conta(client, csrf, "Banco Caixinha")
    r = client.put(
        f"/api/contas/{caixinha}",
        json={"nome": "Banco Caixinha", "tipo": "reserva", "conta_mae_id": banco, "versao": 1},
        headers=escrita(csrf),
    )
    assert r.status_code == 200, r.text
    assert r.json() == {
        "conta_id": caixinha,
        "nome": "Banco Caixinha",
        "conta_beneficio": False,
        "tipo": "reserva",
        "conta_mae_id": banco,
        "versao": 2,
        "linha_credito_id": None,
    }
    r = client.put(
        f"/api/contas/{caixinha}",
        json={"nome": "Outro", "tipo": "reserva", "versao": 1},
        headers=escrita(csrf),
    )
    assert r.status_code == 409, r.text
    assert r.headers["X-Abako-Erro"] == "AB409"  # versão desatualizada
    r = client.put(
        f"/api/contas/{caixinha}",
        json={"nome": "Banco", "tipo": "reserva", "versao": 2},
        headers=escrita(csrf),
    )
    assert r.status_code == 409 and "já existe" in r.json()["detail"]
    assert r.headers["X-Abako-Erro"] == "AB410"  # nome repetido: outro código, mesmo status
    r = client.post(
        "/api/contas",
        json={"nome": "X", "tipo": "corrente", "conta_beneficio": True},
        headers=escrita(csrf),
    )
    assert r.status_code == 422


def test_repetir_chave_de_lancamento_excluido(client: TestClient, usuario: Usuario) -> None:
    """A chave não ressuscita um lançamento excluído: 409, e nada volta a contar."""
    csrf = logar(client, usuario)
    c = criar_conta(client, csrf, "Corrente")
    corpo = {
        "chave": "form-excluido-1",
        "tipo": "debito",
        "data": "2026-02-02",
        "valor": "5",
        "conta_id": c,
    }
    tid = client.post("/api/lancamentos", json=corpo, headers=escrita(csrf)).json()["transacao_id"]
    r = client.delete(f"/api/lancamentos/{tid}", params={"versao": 1}, headers=escrita(csrf))
    assert r.status_code == 204

    r = client.post("/api/lancamentos", json=corpo, headers=escrita(csrf))
    assert r.status_code == 409 and "excluído" in r.json()["detail"]
    assert client.get("/api/lancamentos").json() == []
    assert saldo(client, c, "2026-02-28") == "0.00"


def test_descricao_conta_depois_de_aparar(client: TestClient, usuario: Usuario) -> None:
    csrf = logar(client, usuario)
    c = criar_conta(client, csrf, "Corrente")
    base = {"tipo": "receita", "data": "2026-02-02", "valor": "1", "conta_id": c}
    r = lancar(client, csrf, **base, descricao="  " + "x" * 200 + "  ")
    assert r.status_code == 201 and r.json()["descricao"] == "x" * 200
    assert lancar(client, csrf, **base, descricao="x" * 201).status_code == 422
    assert lancar(client, csrf, **base, descricao="   ").json()["descricao"] is None
