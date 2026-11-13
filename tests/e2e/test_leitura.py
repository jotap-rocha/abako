"""SPEC-012-AC-14: jornada ver a fatura do cartão, o gasto real do mês e os alertas, no navegador.

Os dados (contas, cartão, compras, snapshot) são montados pela API de verdade, só com valores
sintéticos e datas relativas a hoje; a conferência é toda pela tela. Valores esperados calculados
à mão: compra de 100,00 em 2 parcelas e compra de terceiro de 30,00 em 1 parcela, no dia 5 do mês
anterior (fechamento dia 10, então a fatura do mês anterior já fechou).
"""

from __future__ import annotations

from datetime import date, datetime, timedelta
from typing import Any
from zoneinfo import ZoneInfo

import httpx
import pytest
from playwright.sync_api import Page, expect

from tests.backend.conftest import Usuario

pytestmark = [pytest.mark.banco, pytest.mark.e2e]


def _hoje() -> date:
    return datetime.now(ZoneInfo("America/Sao_Paulo")).date()


def _mes_anterior_dia(dia: int) -> date:
    """O `dia` do mês anterior ao de hoje (data de negócio em São Paulo)."""
    ultimo_do_anterior = _hoje().replace(day=1) - timedelta(days=1)
    return ultimo_do_anterior.replace(day=dia)


class Api:
    """Cliente mínimo da API para montar o cenário (login, CSRF e Origin como o navegador)."""

    def __init__(self, base: str, usuario: Usuario) -> None:
        self.http = httpx.Client(base_url=base, headers={"Origin": base})
        r = self.http.post("/api/auth/login", json={"login": usuario.login, "senha": usuario.senha})
        assert r.status_code == 200, r.text
        self.csrf: str = r.json()["csrf_token"]
        self._n = 0

    def post(self, caminho: str, corpo: dict[str, Any]) -> dict[str, Any]:
        r = self.http.post(caminho, json=corpo, headers={"X-CSRF-Token": self.csrf})
        assert r.status_code == 201, (caminho, r.status_code, r.text)
        saida: dict[str, Any] = r.json()
        return saida

    def lancar(self, **campos: Any) -> dict[str, Any]:
        self._n += 1
        return self.post("/api/lancamentos", {"chave": f"e2e-leitura-{self._n:04d}", **campos})


def montar_cenario(base: str, usuario: Usuario) -> None:
    api = Api(base, usuario)
    hoje = _hoje().isoformat()
    compra = _mes_anterior_dia(5).isoformat()

    corrente = api.post("/api/contas", {"nome": "Conta e2e", "tipo": "corrente"})["conta_id"]
    api.post(f"/api/contas/{corrente}/snapshots", {"data": "2026-01-01", "valor": "1000.00"})
    linha = api.post("/api/linhas-credito", {"nome": "Linha e2e", "limite": "5000"})["linha_id"]
    cartao = api.post(
        "/api/contas", {"nome": "Cartão e2e", "tipo": "divida", "linha_credito_id": linha}
    )["conta_id"]
    api.post(f"/api/cartoes/{cartao}/fechamentos", {"dia": 10, "vigente_desde": "2026-01-01"})
    pessoa = api.post("/api/pessoas", {"nome": "Maria e2e"})["pessoa_id"]

    # Cartão: 100,00 em 2 parcelas (50,00 no mês anterior e 50,00 neste) e 30,00 de terceiro.
    api.lancar(
        tipo="credito",
        data=compra,
        valor="100.00",
        parcelas=2,
        conta_id=cartao,
        descricao="Geladeira e2e",
    )
    api.lancar(
        tipo="credito",
        data=compra,
        valor="30.00",
        parcelas=1,
        conta_id=cartao,
        descricao="Presente e2e",
        pessoa_id=pessoa,
    )
    # Conta corrente: receita de 1.000,00 e despesa de 40,00 hoje.
    api.lancar(tipo="receita", data=hoje, valor="1000.00", conta_id=corrente)
    api.lancar(tipo="debito", data=hoje, valor="40.00", conta_id=corrente, descricao="mercado e2e")
    # Saldo informado de 777,00 contra 1.960,00 calculados: divergência de 1.183,00 (R4).
    api.post(f"/api/contas/{corrente}/snapshots", {"data": hoje, "valor": "777.00"})


def test_jornada_leitura(servidor: str, usuario_e2e: Usuario, pagina: Page) -> None:
    montar_cenario(servidor, usuario_e2e)

    pagina.goto(servidor)
    pagina.get_by_label("Login").fill(usuario_e2e.login)
    pagina.get_by_label("Senha", exact=True).fill(usuario_e2e.senha)
    pagina.get_by_role("button", name="Entrar").click()
    expect(pagina.get_by_role("heading", name="Início")).to_be_visible()
    menu = pagina.get_by_role("navigation", name="Principal")

    # Início: receita de caixa e gasto real do mês, como a API calculou (40,00 de débito + 50,00
    # da 2ª parcela da compra própria; a parcela do terceiro não é gasto real).
    expect(pagina.get_by_text("R$ 1.000,00").first).to_be_visible()
    expect(pagina.get_by_text("R$ 90,00")).to_be_visible()

    # Cartões: a fatura do mês anterior já fechou
    menu.get_by_role("link", name="Cartões").click()
    pagina.get_by_role("button", name="Mês anterior").click()
    expect(pagina.get_by_text("Fatura de Cartão e2e")).to_be_visible()
    expect(pagina.get_by_text("Fechada", exact=True)).to_be_visible()
    expect(pagina.get_by_text("R$ 80,00", exact=True)).to_be_visible()
    itens = pagina.get_by_role("list", name="Itens da fatura")
    expect(itens).to_contain_text("Geladeira e2e")
    expect(itens).to_contain_text("parcela 1 de 2")
    expect(itens).to_contain_text("Terceiro: Maria e2e")
    # Limite usado: o valor total das compras (100,00 + 30,00), com parcelas futuras
    expect(pagina.get_by_text("R$ 130,00", exact=True)).to_be_visible()
    expect(pagina.get_by_text("R$ 4.870,00", exact=True)).to_be_visible()
    # Termo técnico explicado
    pagina.get_by_role("button", name="Terceiros").first.click()
    expect(pagina.get_by_role("note")).to_contain_text("não são gasto seu")

    # Gasto do mês: mês corrente e depois o anterior
    menu.get_by_role("link", name="Gasto do mês").click()
    por_conta = pagina.get_by_role("list", name="Gasto real por conta")
    expect(por_conta).to_contain_text("Conta e2e")
    expect(por_conta).to_contain_text("R$ 40,00")
    expect(por_conta).to_contain_text("Cartão e2e")
    expect(por_conta).to_contain_text("R$ 50,00")
    pagina.get_by_role("button", name="Mês anterior").click()
    expect(pagina.locator(".valor-grande").first).to_have_text("R$ 50,00")

    # Alertas: divergência de saldo (R4) com o nome da conta, e o pedido de configuração
    menu.get_by_role("link", name="Alertas").click()
    lista = pagina.get_by_role("list", name="Alertas")
    expect(lista).to_contain_text("Conta e2e")
    expect(lista).to_contain_text("calculou R$ 1.960,00 e você informou R$ 777,00")
    expect(lista).to_contain_text("R$ 1.183,00")
    expect(lista).to_contain_text("pedido de configuração")

    # Sair volta ao login
    pagina.get_by_role("button", name="Sair").click()
    expect(pagina.get_by_label("Login")).to_be_visible()
