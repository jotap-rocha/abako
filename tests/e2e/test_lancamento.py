"""SPEC-012-AC-9: jornada lançar uma despesa, ver o saldo mudar, excluir e ver o saldo voltar.

Tudo passa pela tela e pela API de verdade (sessão, CSRF, idempotência, versão), contra o `tst`.
Só dado sintético: usuário de teste criado e apagado pela fixture.
"""

from __future__ import annotations

import pytest
from playwright.sync_api import Locator, Page, expect

from tests.backend.conftest import Usuario

pytestmark = [pytest.mark.banco, pytest.mark.e2e]


def saldo_da_conta(pagina: Page) -> Locator:
    return pagina.locator(".conta-saldo", has_text="Saldo de Conta e2e:")


def test_lancar_e_ver_saldo(servidor: str, usuario_e2e: Usuario, pagina: Page) -> None:
    pagina.goto(servidor)
    pagina.get_by_label("Login").fill(usuario_e2e.login)
    pagina.get_by_label("Senha", exact=True).fill(usuario_e2e.senha)
    pagina.get_by_role("button", name="Entrar").click()
    expect(pagina.get_by_role("heading", name="Início")).to_be_visible()
    menu = pagina.get_by_role("navigation", name="Principal")

    # Conta com saldo inicial de R$ 1.000,00 em uma data passada
    menu.get_by_role("link", name="Contas").click()
    form_conta = pagina.get_by_role("form", name="Nova conta")
    form_conta.get_by_label("Nome da conta").fill("Conta e2e")
    form_conta.get_by_role("button", name="Criar conta").click()
    pagina.get_by_role("button", name="Informar saldo de Conta e2e").click()
    form_saldo = pagina.get_by_role("form", name="Informar saldo de Conta e2e")
    # O saldo informado vale para o fim do dia: só lançamentos de dias depois dele contam.
    form_saldo.get_by_label("Data do saldo").fill("2026-01-01")
    form_saldo.get_by_label("Saldo no banco (R$)").fill("1.000,00")
    form_saldo.get_by_role("button", name="Salvar saldo").click()
    expect(saldo_da_conta(pagina)).to_have_text("Saldo de Conta e2e: R$ 1.000,00")

    # Lançar uma despesa de R$ 50,00 (hoje: a data já vem preenchida)
    menu.get_by_role("link", name="Lançamentos").click()
    expect(pagina.get_by_text("Nenhum lançamento ainda")).to_be_visible()
    form = pagina.get_by_role("form", name="Novo lançamento")
    form.get_by_label("Valor (R$)").fill("50,00")
    form.get_by_label("Descrição (opcional)").fill("mercado")
    form.get_by_role("button", name="Salvar lançamento").click()
    expect(form.get_by_role("status")).to_contain_text(
        "Lançamento salvo: Despesa (débito) de R$ 50,00"
    )
    lista = pagina.get_by_role("list", name="Lançamentos")
    expect(lista).to_contain_text("R$ 50,00")

    # O saldo da conta é o que o servidor calculou, e continua depois de recarregar
    menu.get_by_role("link", name="Contas").click()
    expect(saldo_da_conta(pagina)).to_have_text("Saldo de Conta e2e: R$ 950,00")
    pagina.reload()
    expect(saldo_da_conta(pagina)).to_have_text("Saldo de Conta e2e: R$ 950,00")

    # Excluir (com confirmação) devolve o saldo
    menu.get_by_role("link", name="Lançamentos").click()
    pagina.get_by_role("button", name="Excluir lançamento", exact=False).first.click()
    pagina.get_by_role("button", name="Confirmar exclusão").click()
    expect(pagina.get_by_text("Lançamento excluído")).to_be_visible()
    expect(pagina.get_by_text("Nenhum lançamento ainda")).to_be_visible()
    menu.get_by_role("link", name="Contas").click()
    expect(saldo_da_conta(pagina)).to_have_text("Saldo de Conta e2e: R$ 1.000,00")
