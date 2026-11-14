"""Guarda global (ADR 014/021): aborta a suíte se o alvo de banco não for o `tst`."""

from __future__ import annotations

import os
import re
from collections.abc import Generator

import pytest

from db.alvo import (
    PAPEIS_RUNTIME,
    VAR_URL_TST,
    AlvoInvalido,
    carregar_env,
    verificar_ambiente_tst,
    verificar_url_papel,
)


def pytest_sessionstart(session: pytest.Session) -> None:
    carregar_env()
    # Valida quando há URL configurada ou o ambiente foi forçado para fora de tst;
    # testes de banco falham sem URL (fixture `url_tst`).
    if os.environ.get(VAR_URL_TST) or os.environ.get("ABAKO_ENV", "tst") != "tst":
        try:
            verificar_ambiente_tst()
            for var, usuario in PAPEIS_RUNTIME.values():
                if os.environ.get(var):
                    verificar_url_papel(os.environ[var], var, usuario)
        except AlvoInvalido as exc:
            pytest.exit(f"ABORTADO: alvo do banco não é `tst`: {exc}", returncode=2)


# Defesa em profundidade: uma URL de conexão com senha nunca pode sair num relatório de falha
# (asserção, locais, captura de log ou stdout). Mascara `://usuario:senha@`.
URL_COM_SENHA = re.compile(r"(://[^:/@\s]+:)[^@\s]+@")


def mascarar_urls(texto: str) -> str:
    return URL_COM_SENHA.sub(r"\1***@", texto)


def mascarar_relatorio(relatorio: pytest.TestReport) -> None:
    """Troca a senha das URLs de conexão por *** no texto do relatório (falha ou erro)."""
    if relatorio.passed:
        return
    if relatorio.longrepr is not None:
        relatorio.longrepr = mascarar_urls(str(relatorio.longrepr))
    relatorio.sections = [(n, mascarar_urls(c)) for n, c in relatorio.sections]


@pytest.hookimpl(wrapper=True)
def pytest_runtest_makereport(
    item: pytest.Item, call: pytest.CallInfo[None]
) -> Generator[None, pytest.TestReport, pytest.TestReport]:
    relatorio = yield
    mascarar_relatorio(relatorio)
    return relatorio
