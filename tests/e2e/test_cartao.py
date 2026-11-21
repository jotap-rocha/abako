"""SPEC-012-AC-30: jornada do cadastro do cartão, no navegador de verdade.

Dados sintéticos. O usuário começa sem nenhum cartão: cria a linha de crédito e o cartão pela tela
(com fechamento no dia 31), lança uma compra no crédito de 123,45 em 1 parcela datada do 1º dia do
mês atual e a vê na fatura. A data fixa no dia 1 (igual ao "vale a partir de" padrão, nunca futura
e antes de qualquer fechamento do mês) evita depender do dia em que o teste roda: a compra feita no
próprio dia do fechamento cairia na fatura seguinte (ADR 043).
"""

from __future__ import annotations

import pytest
from playwright.sync_api import Page, expect

from tests.backend.conftest import Usuario
from tests.e2e.test_formularios import _entrar
from tests.e2e.test_leitura import _hoje

pytestmark = [pytest.mark.banco, pytest.mark.e2e]


def test_criar_cartao_com_fechamento_lancar_compra_e_ver_na_fatura(
    servidor: str, usuario_e2e: Usuario, pagina: Page
) -> None:
    _entrar(pagina, servidor, usuario_e2e)
    menu = pagina.get_by_role("navigation", name="Principal")

    # Sem cartão: o estado vazio convida ao formulário.
    menu.get_by_role("link", name="Cartões").click()
    expect(pagina.get_by_text("Nenhum cartão ainda")).to_be_visible()

    form = pagina.get_by_role("form", name="Novo cartão")
    form.get_by_label("Nome da linha").fill("Linha e2e")
    form.get_by_label("Limite (R$)").fill("5.000,00")
    form.get_by_label("Nome do cartão").fill("Cartão e2e")
    form.get_by_label("Dia de fechamento (opcional)").fill("31")
    form.get_by_role("button", name="Criar cartão").click()
    expect(form.get_by_role("status")).to_contain_text('Cartão "Cartão e2e" criado')

    # O cartão novo aparece com o limite que o servidor devolveu.
    expect(pagina.get_by_text("Fatura de Cartão e2e")).to_be_visible()
    expect(pagina.get_by_text("R$ 5.000,00").first).to_be_visible()

    # Compra no crédito, 1 parcela.
    menu.get_by_role("link", name="Lançamentos").click()
    lanc = pagina.get_by_role("form", name="Novo lançamento")
    lanc.get_by_label("Tipo", exact=True).select_option(label="Compra no cartão de crédito")
    lanc.get_by_label("Cartão", exact=True).select_option(label="Cartão e2e")
    lanc.get_by_label("Parcelas").select_option(label="À vista (1x)")
    lanc.get_by_label("Data", exact=True).fill(_hoje().replace(day=1).isoformat())
    lanc.get_by_label("Valor total da compra (R$)").fill("123,45")
    lanc.get_by_label("Descrição (opcional)").fill("compra cartao e2e")
    lanc.get_by_role("button", name="Salvar lançamento").click()
    expect(pagina.get_by_role("status").first).to_contain_text("Lançamento salvo")

    # A compra aparece na fatura do mês, como o servidor calculou.
    menu.get_by_role("link", name="Cartões").click()
    itens = pagina.get_by_role("list", name="Itens da fatura")
    expect(itens).to_contain_text("compra cartao e2e")
    expect(itens).to_contain_text("R$ 123,45")
