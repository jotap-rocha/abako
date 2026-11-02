"""Guarda global (ADR 014/021): aborta a suíte se o alvo de banco não for o `tst`."""

from __future__ import annotations

import os

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
