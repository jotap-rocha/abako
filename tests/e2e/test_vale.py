"""SPEC-013-AC-14/15..: jornada do vale no navegador de verdade (dados sintéticos).

Marca o VR pela tela, lança uma despesa com bolso e confere a página do vale. Valores esperados
calculados à mão: crédito de 1000,00 no mês, base de trabalho 200,00 (trabalho 200,00; pessoal
800,00); despesa de 50,00 no bolso trabalho deixa trabalho com 150,00, pessoal com 800,00, sobra
de 950,00 e saldo total de 950,00 (1000,00 - 50,00).
"""

from __future__ import annotations

import re

import pytest
from playwright.sync_api import Page, expect

from tests.backend.conftest import Usuario
from tests.e2e.test_formularios import _entrar
from tests.e2e.test_leitura import Api, _hoje

pytestmark = [pytest.mark.banco, pytest.mark.e2e]


def test_marcar_vr_lancar_com_bolso_e_ver_a_pagina_do_vale(
    servidor: str, usuario_e2e: Usuario, pagina: Page
) -> None:
    api = Api(servidor, usuario_e2e)
    vr = api.post("/api/contas", {"nome": "VR e2e", "tipo": "beneficio", "conta_beneficio": True})[
        "conta_id"
    ]
    api.post(f"/api/contas/{vr}/snapshots", {"data": "2026-01-01", "valor": "0.00"})
    api.lancar(tipo="receita", data=_hoje().isoformat(), valor="1000.00", conta_id=vr)

    _entrar(pagina, servidor, usuario_e2e)
    menu = pagina.get_by_role("navigation", name="Principal")

    # Sem marcação: a página explica e oferece o formulário.
    menu.get_by_role("link", name="Vale").click()
    expect(pagina.get_by_text("Nenhuma conta marcada como VR")).to_be_visible()
    form = pagina.get_by_role("form", name="Marcar a conta do VR")
    form.get_by_label("Conta do VR").select_option(label="VR e2e")
    form.get_by_role("button", name="Salvar marcação do VR").click()
    expect(pagina.get_by_role("region", name="Bolso Trabalho")).to_be_visible()

    # Despesa no VR pede o bolso.
    menu.get_by_role("link", name="Lançamentos").click()
    lanc = pagina.get_by_role("form", name="Novo lançamento")
    lanc.get_by_label("Conta de onde saiu").select_option(label="VR e2e")
    lanc.get_by_label("Bolso").select_option(label="Trabalho")
    lanc.get_by_label("Valor (R$)").fill("50,00")
    lanc.get_by_role("button", name="Salvar lançamento").click()
    expect(pagina.get_by_role("status").first).to_contain_text("Lançamento salvo")
    expect(pagina.get_by_role("list", name="Lançamentos")).to_contain_text("bolso trabalho")

    # Página do vale com os números do servidor.
    menu.get_by_role("link", name="Vale").click()
    trabalho = pagina.get_by_role("region", name="Bolso Trabalho")
    expect(trabalho).to_contain_text("R$ 150,00")
    expect(trabalho).to_contain_text("R$ 50,00")
    expect(pagina.get_by_role("region", name="Bolso Pessoal")).to_contain_text("R$ 800,00")
    expect(pagina.get_by_text("R$ 950,00").first).to_be_visible()
    lista = pagina.get_by_role("list", name="Contas de benefício")
    expect(lista).to_contain_text("vale-refeição")

    # A tela principal não fala do vale.
    menu.get_by_role("link", name="Início").click()
    expect(pagina.get_by_role("heading", name="Início")).to_be_visible()
    expect(pagina.get_by_role("main")).not_to_contain_text(re.compile("vale", re.IGNORECASE))
