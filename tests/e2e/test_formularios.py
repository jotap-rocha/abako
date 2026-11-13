"""SPEC-012-AC-15/16/18: jornadas dos formulários restantes, no navegador de verdade.

Os dados de base (contas, cartão) vêm da API, só com valores sintéticos; os formulários são
preenchidos pela tela. Valores esperados calculados à mão: compra de terceiro de 100,00 e repasse
de 30,00 deixam a receber 70,00; estorno de compra sem nada pago devolve o limite por inteiro.
"""

from __future__ import annotations

from datetime import timedelta

import pytest
from playwright.sync_api import Page, expect

from tests.backend.conftest import Usuario
from tests.e2e.test_leitura import Api, _hoje

pytestmark = [pytest.mark.banco, pytest.mark.e2e]


def _montar_contas(base: str, usuario: Usuario) -> tuple[Api, int]:
    api = Api(base, usuario)
    corrente = api.post("/api/contas", {"nome": "Conta e2e", "tipo": "corrente"})["conta_id"]
    api.post(f"/api/contas/{corrente}/snapshots", {"data": "2026-01-01", "valor": "1000.00"})
    linha = api.post("/api/linhas-credito", {"nome": "Linha e2e", "limite": "5000"})["linha_id"]
    cartao = api.post(
        "/api/contas", {"nome": "Cartão e2e", "tipo": "divida", "linha_credito_id": linha}
    )["conta_id"]
    api.post(f"/api/cartoes/{cartao}/fechamentos", {"dia": 10, "vigente_desde": "2026-01-01"})
    return api, cartao


def _entrar(pagina: Page, servidor: str, usuario: Usuario) -> None:
    pagina.goto(servidor)
    pagina.get_by_label("Login").fill(usuario.login)
    pagina.get_by_label("Senha", exact=True).fill(usuario.senha)
    pagina.get_by_role("button", name="Entrar").click()
    expect(pagina.get_by_role("heading", name="Início")).to_be_visible()


def test_pessoa_compra_de_terceiro_repasse_e_a_receber(
    servidor: str, usuario_e2e: Usuario, pagina: Page
) -> None:
    _montar_contas(servidor, usuario_e2e)
    _entrar(pagina, servidor, usuario_e2e)
    menu = pagina.get_by_role("navigation", name="Principal")

    # Cadastra a pessoa.
    menu.get_by_role("link", name="Pessoas").click()
    pagina.get_by_label("Nome", exact=True).fill("Pessoa e2e")
    pagina.get_by_role("button", name="Cadastrar pessoa").click()
    expect(pagina.get_by_role("list", name="Pessoas")).to_contain_text("Pessoa e2e")

    # Compra de terceiro: 100,00 em 2 parcelas, toda da pessoa.
    menu.get_by_role("link", name="Lançamentos").click()
    form = pagina.get_by_role("form", name="Novo lançamento")
    form.get_by_label("Tipo", exact=True).select_option(label="Compra no cartão de crédito")
    form.get_by_label("Cartão", exact=True).select_option(label="Cartão e2e")
    form.get_by_label("Parcelas").select_option(label="2x")
    form.get_by_label("De quem é a compra").select_option(label="Pessoa e2e")
    form.get_by_label("Valor total da compra (R$)").fill("100,00")
    form.get_by_role("button", name="Salvar lançamento").click()
    expect(pagina.get_by_role("status").first).to_contain_text("Lançamento salvo")
    expect(pagina.get_by_role("list", name="Lançamentos")).to_contain_text("compra de Pessoa e2e")

    # Repasse de 30,00 na conta corrente.
    form.get_by_label("Tipo", exact=True).select_option(label="Repasse recebido de terceiro")
    form.get_by_label("Conta corrente que recebeu").select_option(label="Conta e2e")
    form.get_by_label("Quem repassou").select_option(label="Pessoa e2e")
    form.get_by_label("Valor (R$)").fill("30,00")
    form.get_by_role("button", name="Salvar lançamento").click()
    expect(pagina.get_by_role("list", name="Lançamentos")).to_contain_text("repasse de Pessoa e2e")

    # A receber: dívida 100,00, repassado 30,00, a receber 70,00 (como o servidor calculou).
    menu.get_by_role("link", name="Pessoas").click()
    pessoa = pagina.get_by_role("list", name="Pessoas")
    expect(pessoa).to_contain_text("R$ 100,00")
    expect(pessoa).to_contain_text("R$ 30,00")
    expect(pessoa).to_contain_text("R$ 70,00")


def test_estornar_compra(servidor: str, usuario_e2e: Usuario, pagina: Page) -> None:
    api, cartao = _montar_contas(servidor, usuario_e2e)
    compra = (_hoje() - timedelta(days=3)).isoformat()
    api.lancar(
        tipo="credito",
        data=compra,
        valor="100.00",
        parcelas=1,
        conta_id=cartao,
        descricao="compra e2e",
    )
    _entrar(pagina, servidor, usuario_e2e)
    pagina.get_by_role("navigation", name="Principal").get_by_role(
        "link", name="Lançamentos"
    ).click()

    lista = pagina.get_by_role("list", name="Lançamentos")
    lista.get_by_role("button", name="Estornar compra").click()
    # As regras aparecem antes de confirmar.
    expect(pagina.get_by_role("form", name="Estornar compra")).to_contain_text(
        "o cartão fica imutável"
    )
    pagina.get_by_role("button", name="Confirmar estorno").click()

    # Nada estava pago: estorno integral, limite devolvido por inteiro (100,00).
    resultado = pagina.get_by_role("status", name="Resultado do estorno")
    expect(resultado).to_contain_text("Estorno integral")
    expect(resultado).to_contain_text("R$ 100,00")
    # A lista foi buscada de novo: aparece a linha do estorno.
    expect(lista).to_contain_text("Estorno de compra")
