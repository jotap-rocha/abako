"""Limites de entrada da API (ADR 049 item 8): `versao` acima do integer do banco e `mes` com
caractere de controle ou muito longo são 422 (nunca 500), sem eco do valor recebido."""

from __future__ import annotations

from typing import Any

import pytest
from fastapi.testclient import TestClient

from tests.backend.conftest import ORIGEM, Usuario
from tests.backend.util_r2_api import Cenario, escrita

pytestmark = pytest.mark.banco

TETO = 2**31 - 1
LITERAL_MES = "o mês precisa estar no formato AAAA-MM"


def codigo(r: Any) -> tuple[int, str | None]:
    return r.status_code, r.headers.get("X-Abako-Erro")


def test_versao_de_lancamento_tem_teto_do_integer(client: TestClient, usuario: Usuario) -> None:
    """Edição e exclusão de lançamento: `versao` 2**31 é 422; no teto, 409 (versão velha)."""
    c = Cenario(client, usuario)
    lanc = c.debito("2026-05-06", "10.00")
    url = f"/api/lancamentos/{lanc['transacao_id']}"
    corpo = {
        "tipo": "debito",
        "data": "2026-05-06",
        "valor": "10.00",
        "conta_id": c.corrente,
    }
    assert (
        client.put(url, json=corpo | {"versao": 2**31}, headers=escrita(c.csrf)).status_code == 422
    )
    assert codigo(client.put(url, json=corpo | {"versao": TETO}, headers=escrita(c.csrf))) == (
        409,
        "AB409",
    )
    r = client.delete(url, params={"versao": 2**31}, headers=escrita(c.csrf))
    assert r.status_code == 422
    r = client.delete(url, params={"versao": TETO}, headers=escrita(c.csrf))
    assert codigo(r) == (409, "AB409")
    # nada foi gravado pelas tentativas
    assert client.get(url).json()["versao"] == lanc["versao"]


def test_versao_do_estorno_tem_teto_do_integer(client: TestClient, usuario: Usuario) -> None:
    c = Cenario(client, usuario)
    cartao = c.cartao(10, 20)
    compra = c.compra(cartao, "2026-04-20", "100.00")
    url = f"/api/lancamentos/{compra['transacao_id']}/estorno"
    corpo = {"data": "2026-04-25"}
    assert (
        client.post(url, json=corpo | {"versao": 2**31}, headers=escrita(c.csrf)).status_code == 422
    )
    r = client.post(url, json=corpo | {"versao": TETO}, headers=escrita(c.csrf))
    assert codigo(r) == (409, "AB409")


def test_versao_de_conta_e_de_linha_de_credito_tem_teto_do_integer(
    client: TestClient, usuario: Usuario
) -> None:
    c = Cenario(client, usuario)
    url = f"/api/contas/{c.corrente}"
    conta = {"nome": "Corrente", "tipo": "corrente"}
    assert (
        client.put(url, json=conta | {"versao": 2**31}, headers=escrita(c.csrf)).status_code == 422
    )
    r = client.put(url, json=conta | {"versao": TETO}, headers=escrita(c.csrf))
    assert codigo(r) == (409, "AB409")

    linha = client.post(
        "/api/linhas-credito", json={"nome": "Linha", "limite": "1000"}, headers=escrita(c.csrf)
    )
    assert linha.status_code == 201, linha.text
    url = f"/api/linhas-credito/{linha.json()['linha_id']}"
    corpo = {"nome": "Linha", "limite": "1000"}
    assert (
        client.put(url, json=corpo | {"versao": 2**31}, headers=escrita(c.csrf)).status_code == 422
    )
    r = client.put(url, json=corpo | {"versao": TETO}, headers=escrita(c.csrf))
    assert codigo(r) == (409, "AB409")


def test_versao_sem_csrf_continua_403(client: TestClient, usuario: Usuario) -> None:
    c = Cenario(client, usuario)
    r = client.delete(
        f"/api/lancamentos/{c.debito('2026-05-06', '1.00')['transacao_id']}",
        params={"versao": 1},
        headers=ORIGEM,
    )
    assert r.status_code == 403


@pytest.mark.parametrize(
    "mes", ["2026-05\x00", "2026-05\n", "2026\x07-05", "x" * 500, "2026-05 " * 3]
)
def test_mes_longo_ou_com_controle_e_ab422_literal_no_gasto_real_e_na_receita(
    client: TestClient, usuario: Usuario, mes: str
) -> None:
    """`GET /api/gasto-real` e `GET /api/receita`: 422/AB422 literal, sem eco, nunca 500; a
    próxima chamada válida na mesma conexão funciona."""
    Cenario(client, usuario)
    for rota in ("/api/gasto-real", "/api/receita"):
        r = client.get(rota, params={"mes": mes})
        assert codigo(r) == (422, "AB422"), (rota, r.text)
        assert r.json()["detail"] == LITERAL_MES
        assert mes.strip() not in r.text
    assert client.get("/api/gasto-real", params={"mes": "2026-05"}).status_code == 200
    assert client.get("/api/receita", params={"mes": "2026-05"}).status_code == 200
