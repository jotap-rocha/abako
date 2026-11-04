"""SPEC-012-AC-6: jornada login → criar conta → informar saldo → ver saldo, no navegador.

Tudo passa pela tela e pela API de verdade (sessão, CSRF, Host/Origin), contra o `tst`.
Só dado sintético: usuário de teste criado e apagado pela fixture.
"""

from __future__ import annotations

import re

import pytest
from playwright.sync_api import Locator, Page, expect

from tests.backend.conftest import Usuario

pytestmark = [pytest.mark.banco, pytest.mark.e2e]


def saldo_da_conta(pagina: Page) -> Locator:
    """O saldo exibido: o texto para leitor de tela ("Saldo de X:") e o valor formatado."""
    return pagina.locator(".conta-saldo", has_text="Saldo de Conta e2e:")


def test_login_e_saldos(servidor: str, usuario_e2e: Usuario, pagina: Page) -> None:
    pagina.goto(servidor)

    # Login
    pagina.get_by_label("Login").fill(usuario_e2e.login)
    pagina.get_by_label("Senha", exact=True).fill(usuario_e2e.senha)
    pagina.get_by_role("button", name="Entrar").click()
    expect(pagina.get_by_role("heading", name="Início")).to_be_visible()

    # Contas: começa vazio
    menu = pagina.get_by_role("navigation", name="Principal")
    menu.get_by_role("link", name="Contas").click()
    expect(pagina.get_by_text("Nenhuma conta ainda")).to_be_visible()

    # Criar conta (POST com CSRF)
    form_conta = pagina.get_by_role("form", name="Nova conta")
    form_conta.get_by_label("Nome da conta").fill("Conta e2e")
    form_conta.get_by_role("button", name="Criar conta").click()
    expect(form_conta.get_by_role("status")).to_contain_text("Conta “Conta e2e” criada")
    expect(saldo_da_conta(pagina)).to_have_text("Saldo de Conta e2e: R$ 0,00")

    # Informar o saldo do banco: o primeiro é o saldo inicial
    pagina.get_by_role("button", name="Informar saldo de Conta e2e").click()
    form_saldo = pagina.get_by_role("form", name="Informar saldo de Conta e2e")
    form_saldo.get_by_label("Saldo no banco (R$)").fill("1.234,56")
    form_saldo.get_by_role("button", name="Salvar saldo").click()
    expect(form_saldo.get_by_role("status")).to_contain_text(
        "Saldo inicial registrado: R$ 1.234,56"
    )

    # O saldo mostrado é o que o servidor calculou, e continua depois de recarregar a página
    expect(saldo_da_conta(pagina)).to_have_text("Saldo de Conta e2e: R$ 1.234,56")
    pagina.reload()
    expect(saldo_da_conta(pagina)).to_have_text("Saldo de Conta e2e: R$ 1.234,56")
    expect(pagina.get_by_text(re.compile(r"Último saldo informado: R\$ 1\.234,56"))).to_be_visible()

    # Alertas: saldo inicial nunca diverge
    menu.get_by_role("link", name="Alertas").click()
    expect(pagina.get_by_text("Nenhuma divergência")).to_be_visible()

    # Sair volta ao login
    pagina.get_by_role("button", name="Sair").click()
    expect(pagina.get_by_label("Login")).to_be_visible()
