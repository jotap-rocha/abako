"""API do estorno (SPEC-006, ADR 044): estorno da compra a crédito, recusas de edição/exclusão e
fatura com o crédito. Valores esperados vêm de F-EST-01..06 (calculados à mão); dinheiro é texto."""

from __future__ import annotations

from collections.abc import Iterator
from typing import Any

import pytest
from fastapi.testclient import TestClient

from tests.backend.conftest import ORIGEM, Usuario, apagar_usuarios, criar_usuario, logar
from tests.backend.test_credito_api import (
    comprar,
    criar_cartao,
    criar_conta,
    criar_linha,
    escrita,
    saldo,
)

pytestmark = pytest.mark.banco

# Compra das fixtures F-EST: 400,00 em 4x, fechamento dia 10; comprada em 05/03, a 1ª parcela cai
# na fatura de 2026-03 (parcelas de 100,00 em 03, 04, 05 e 06).
DATA_COMPRA = "2026-03-05"


@pytest.fixture
def outro_usuario(esquema: str) -> Iterator[Usuario]:
    u = criar_usuario(esquema, "o")
    yield u
    apagar_usuarios(esquema, [u])


def comprar_400(client: TestClient, csrf: str, cartao: int, chave: str = "compra-0001") -> Any:
    r = comprar(client, csrf, cartao, chave=chave, data=DATA_COMPRA, valor="400.00", parcelas=4)
    assert r.status_code == 201, r.text
    return r.json()


def pagar(
    client: TestClient, csrf: str, corrente: int, cartao: int, valor: str, chave: str = "pgto-0001"
) -> Any:
    r = client.post(
        "/api/lancamentos",
        json={
            "chave": chave,
            "tipo": "transferencia",
            "data": "2026-03-20",
            "valor": valor,
            "conta_id": corrente,
            "conta_destino_id": cartao,
        },
        headers=escrita(csrf),
    )
    assert r.status_code == 201, r.text
    return r.json()


def estornar(
    client: TestClient, csrf: str, compra: dict[str, Any], data: str, **campos: Any
) -> Any:
    corpo = {"versao": compra["versao"], "data": data, **campos}
    return client.post(
        f"/api/lancamentos/{compra['transacao_id']}/estorno", json=corpo, headers=escrita(csrf)
    )


def fatura(client: TestClient, cartao: int, competencia: str) -> Any:
    r = client.get(f"/api/cartoes/{cartao}/faturas/{competencia}")
    assert r.status_code == 200, r.text
    return r.json()


def cenario(client: TestClient, usuario: Usuario) -> tuple[str, int, int]:
    csrf = logar(client, usuario)
    cartao = criar_cartao(client, csrf, criar_linha(client, csrf))
    corrente = criar_conta(client, csrf, "Corrente")
    return csrf, cartao, corrente


def test_estorno_integral_f_est_01(client: TestClient, usuario: Usuario) -> None:
    """SPEC-006-AC-1: nada pago, devolve os 400,00 e não movimenta a conta corrente."""
    csrf, cartao, corrente = cenario(client, usuario)
    compra = comprar_400(client, csrf, cartao)
    assert saldo(client, cartao, "2026-03-31") == "-400.00"

    r = estornar(client, csrf, compra, "2026-03-08", descricao="  devolvida ")
    assert r.status_code == 201, r.text
    corpo = r.json()
    assert corpo | {"estorno_id": 0} == {
        "estorno_id": 0,
        "competencia_credito": "2026-03",
        "total": "400.00",
        "pago": "0.00",
        "limite_devolvido": "400.00",
    }
    assert saldo(client, cartao, "2026-03-31") == "0.00"
    assert saldo(client, corrente, "2026-03-31") == "0.00"
    # Fatura: a compra sai de 2026-03 em diante e não há crédito (P = 0).
    for competencia in ("2026-03", "2026-04", "2026-05", "2026-06"):
        f = fatura(client, cartao, competencia)
        assert (f["total"], f["itens"]) == ("0.00", []), competencia

    # A compra original segue na listagem; o estorno é um lançamento do tipo estorno.
    lista = client.get("/api/lancamentos").json()
    por_tipo = {item["tipo"]: item for item in lista}
    assert por_tipo["credito"]["transacao_id"] == compra["transacao_id"]
    estorno = por_tipo["estorno"]
    assert (estorno["transacao_id"], estorno["valor"], estorno["conta_id"]) == (
        corpo["estorno_id"],
        "400.00",
        cartao,
    )
    assert (estorno["estorno_de"], estorno["estorno_credito"]) == (compra["transacao_id"], "0.00")
    assert estorno["descricao"] == "devolvida"
    assert client.get(f"/api/lancamentos/{corpo['estorno_id']}").json()["tipo"] == "estorno"


def test_estorno_com_parcela_paga_f_est_02(client: TestClient, usuario: Usuario) -> None:
    """SPEC-006-AC-2 e AC-11: paga 100,00 vira crédito na próxima fatura aberta; devolve 300,00."""
    csrf, cartao, corrente = cenario(client, usuario)
    compra = comprar_400(client, csrf, cartao)
    pagar(client, csrf, corrente, cartao, "100.00")

    # 25/03 passa do dia de fechamento (10): o crédito cai na fatura de 2026-04.
    r = estornar(client, csrf, compra, "2026-03-25")
    assert r.status_code == 201, r.text
    assert r.json() | {"estorno_id": 0} == {
        "estorno_id": 0,
        "competencia_credito": "2026-04",
        "total": "400.00",
        "pago": "100.00",
        "limite_devolvido": "300.00",
    }
    # Fatura anterior ao crédito não muda: a parcela 1 segue em 2026-03.
    f03 = fatura(client, cartao, "2026-03")
    assert f03["total"] == "100.00"
    assert [(i["parcela"], i["valor"]) for i in f03["itens"]] == [(1, "100.00")]
    # Na competência do estorno a compra sai e o crédito P aparece como item negativo.
    f04 = fatura(client, cartao, "2026-04")
    assert f04["total"] == "-100.00"
    assert [i["valor"] for i in f04["itens"]] == ["-100.00"]
    assert f04["itens"][0]["transacao_id"] == r.json()["estorno_id"]
    assert fatura(client, cartao, "2026-05")["total"] == "0.00"
    # Saldo: -400 + 100 (pagamento) + 400 (estorno); a conta corrente só tem o pagamento.
    assert saldo(client, cartao, "2026-03-31") == "100.00"
    assert saldo(client, corrente, "2026-03-31") == "-100.00"


def test_estorno_com_parcela_paga_em_parte_f_est_03(client: TestClient, usuario: Usuario) -> None:
    """SPEC-006-AC-4: pago 150,00 (parcela 2 só em parte) vira crédito; devolve 250,00."""
    csrf, cartao, corrente = cenario(client, usuario)
    compra = comprar_400(client, csrf, cartao)
    pagar(client, csrf, corrente, cartao, "150.00")
    assert saldo(client, cartao, "2026-03-31") == "-250.00"

    r = estornar(client, csrf, compra, "2026-03-25")
    assert r.status_code == 201, r.text
    assert r.json() | {"estorno_id": 0} == {
        "estorno_id": 0,
        "competencia_credito": "2026-04",
        "total": "400.00",
        "pago": "150.00",
        "limite_devolvido": "250.00",
    }
    assert saldo(client, cartao, "2026-03-31") == "150.00"
    assert fatura(client, cartao, "2026-04")["total"] == "-150.00"


def test_recusa_editar_e_excluir_compra_com_parte_paga_f_est_06(
    client: TestClient, usuario: Usuario
) -> None:
    """SPEC-006-AC-8: compra com parte paga não se edita nem se exclui (422, nada muda); compra
    sem nada pago em outro cartão continua editável e excluível."""
    csrf, cartao, corrente = cenario(client, usuario)
    compra = comprar_400(client, csrf, cartao)
    pagar(client, csrf, corrente, cartao, "150.00")
    id_compra = compra["transacao_id"]

    edicao = {
        "tipo": "credito",
        "data": DATA_COMPRA,
        "valor": "600.00",
        "parcelas": 4,
        "conta_id": cartao,
        "versao": 1,
    }
    r = client.put(f"/api/lancamentos/{id_compra}", json=edicao, headers=escrita(csrf))
    assert r.status_code == 422, r.text
    assert r.headers["X-Abako-Erro"] == "AB422"
    assert "parte paga" in r.json()["detail"] and "editada" in r.json()["detail"]
    r = client.delete(f"/api/lancamentos/{id_compra}", params={"versao": 1}, headers=escrita(csrf))
    assert r.status_code == 422, r.text
    assert r.headers["X-Abako-Erro"] == "AB422"
    assert "excluída" in r.json()["detail"]

    vigente = client.get(f"/api/lancamentos/{id_compra}").json()
    assert (vigente["valor"], vigente["parcelas"], vigente["versao"]) == ("400.00", 4, 1)
    assert saldo(client, cartao, "2026-03-31") == "-250.00"

    # Outro cartão, sem pagamento: edita e exclui normalmente.
    livre = criar_cartao(client, csrf, criar_linha(client, csrf, "Linha B"), "Cartão B")
    sem_pago = comprar_400(client, csrf, livre, chave="compra-0002")
    r = client.put(
        f"/api/lancamentos/{sem_pago['transacao_id']}",
        json=edicao | {"conta_id": livre, "valor": "200.00"},
        headers=escrita(csrf),
    )
    assert r.status_code == 200 and r.json()["valor"] == "200.00", r.text
    r = client.delete(
        f"/api/lancamentos/{sem_pago['transacao_id']}",
        params={"versao": 2},
        headers=escrita(csrf),
    )
    assert r.status_code == 204, r.text


def test_depois_do_estorno_nada_do_cartao_se_edita(client: TestClient, usuario: Usuario) -> None:
    """SPEC-006-AC-10: com estorno no cartão, pagamento, compra estornada, outra compra e o
    estorno são recusados (editar e excluir) com mensagem clara; lançamento novo é aceito."""
    csrf, cartao, corrente = cenario(client, usuario)
    compra = comprar_400(client, csrf, cartao)
    outra = comprar(client, csrf, cartao, chave="compra-0002", valor="50.00", parcelas=1).json()
    pgto = pagar(client, csrf, corrente, cartao, "100.00")
    r = estornar(client, csrf, compra, "2026-03-25")
    assert r.status_code == 201, r.text
    estorno_id = r.json()["estorno_id"]

    edicao_pgto = {
        "tipo": "transferencia",
        "data": "2026-03-20",
        "valor": "10.00",
        "conta_id": corrente,
        "conta_destino_id": cartao,
        "versao": pgto["versao"],
    }
    edicao_compra = {
        "tipo": "credito",
        "data": DATA_COMPRA,
        "valor": "400.00",
        "parcelas": 4,
        "conta_id": cartao,
        "versao": 1,
    }
    edicao_estorno = edicao_compra | {"valor": "1.00", "parcelas": 1}
    alvos = [
        (pgto["transacao_id"], edicao_pgto, "pagamento"),
        (compra["transacao_id"], edicao_compra, "estornada"),
        (outra["transacao_id"], edicao_compra | {"valor": "50.00", "parcelas": 1}, "estorno"),
        (estorno_id, edicao_estorno, "estorno"),
    ]
    for id_alvo, corpo, trecho in alvos:
        r = client.put(f"/api/lancamentos/{id_alvo}", json=corpo, headers=escrita(csrf))
        assert r.status_code == 422, (trecho, r.text)
        assert r.headers["X-Abako-Erro"] == "AB422"
        assert trecho in r.json()["detail"], (trecho, r.json())
        r = client.delete(
            f"/api/lancamentos/{id_alvo}", params={"versao": 1}, headers=escrita(csrf)
        )
        assert r.status_code == 422, (trecho, r.text)
        assert r.headers["X-Abako-Erro"] == "AB422"
    # Nada mudou: saldo = -400 - 50 + 100 + 400.
    assert saldo(client, cartao, "2026-03-31") == "50.00"

    # Lançamentos novos no cartão continuam permitidos.
    assert (
        comprar(client, csrf, cartao, chave="compra-0003", valor="20.00", parcelas=1).status_code
        == 201
    )
    pagar(client, csrf, corrente, cartao, "5.00", chave="pgto-0002")


def test_estorno_duplicado_versao_e_regras(client: TestClient, usuario: Usuario) -> None:
    """Segundo estorno da mesma compra: 409/AB410; versão velha: 409/AB409; só crédito, com data
    válida; sem CSRF: 403."""
    csrf, cartao, corrente = cenario(client, usuario)
    compra = comprar_400(client, csrf, cartao)

    r = estornar(client, csrf, compra | {"versao": 7}, "2026-03-08")
    assert r.status_code == 409 and r.headers["X-Abako-Erro"] == "AB409", r.text
    r = estornar(client, csrf, compra, "2026-03-04")  # antes da compra
    assert r.status_code == 422 and r.headers["X-Abako-Erro"] == "AB422", r.text
    r = estornar(client, csrf, compra, "2099-01-01")  # futura
    assert r.status_code == 422 and r.headers["X-Abako-Erro"] == "AB422", r.text
    r = client.post(
        f"/api/lancamentos/{compra['transacao_id']}/estorno",
        json={"versao": 1, "data": "2026-03-08"},
        headers=ORIGEM,
    )
    assert r.status_code == 403, r.text
    assert estornar(client, csrf, compra, "2026-03-08", descricao="x" * 201).status_code == 422

    assert estornar(client, csrf, compra, "2026-03-08").status_code == 201
    r = estornar(client, csrf, compra, "2026-03-09")
    assert r.status_code == 409 and r.headers["X-Abako-Erro"] == "AB410", r.text
    assert "já foi estornada" in r.json()["detail"]
    assert len([i for i in client.get("/api/lancamentos").json() if i["tipo"] == "estorno"]) == 1

    # Só compra a crédito se estorna: um pagamento (transferência) é recusado; id inexistente, 404.
    pgto = pagar(client, csrf, corrente, cartao, "10.00")
    r = estornar(client, csrf, pgto, "2026-03-25")
    assert r.status_code == 422 and r.headers["X-Abako-Erro"] == "AB422", r.text
    r = estornar(client, csrf, {"transacao_id": 999999999, "versao": 1}, "2026-03-25")
    assert r.status_code == 404 and r.headers["X-Abako-Erro"] == "AB404", r.text


def test_estorno_isolamento_entre_usuarios(
    client: TestClient, usuario: Usuario, outro_usuario: Usuario
) -> None:
    """INV-13: a compra de outro usuário dá 404 e nada é gravado; o user_id do corpo é ignorado."""
    csrf, cartao, _ = cenario(client, usuario)
    compra = comprar_400(client, csrf, cartao)

    client.cookies.clear()
    csrf_outro = logar(client, outro_usuario)
    r = client.post(
        f"/api/lancamentos/{compra['transacao_id']}/estorno",
        json={"versao": 1, "data": "2026-03-08", "user_id": 1},
        headers=escrita(csrf_outro),
    )
    assert r.status_code == 404 and r.headers["X-Abako-Erro"] == "AB404", r.text
    assert client.get("/api/lancamentos").json() == []

    client.cookies.clear()
    logar(client, usuario)
    tipos = [i["tipo"] for i in client.get("/api/lancamentos").json()]
    assert tipos == ["credito"]
    assert saldo(client, cartao, "2026-03-31") == "-400.00"


def test_estorno_valores_sao_texto_com_duas_casas(client: TestClient, usuario: Usuario) -> None:
    """INV-14: total, pago e limite devolvido são texto "0.00", nunca número nem "0"."""
    csrf, cartao, _ = cenario(client, usuario)
    compra = comprar_400(client, csrf, cartao)
    r = estornar(client, csrf, compra, "2026-03-08")
    corpo = r.json()
    for campo in ("total", "pago", "limite_devolvido"):
        assert isinstance(corpo[campo], str), campo
    assert corpo["pago"] == "0.00"
    assert isinstance(corpo["estorno_id"], int)
