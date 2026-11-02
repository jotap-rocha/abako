"""Guarda global (ADR 014/021): aborta a suíte se o alvo de banco não for o `tst`."""

from __future__ import annotations

import os

import pytest

from db.alvo import VAR_URL_TST, AlvoInvalido, carregar_env, verificar_ambiente_tst


def pytest_sessionstart(session: pytest.Session) -> None:
    carregar_env()
    # Valida quando há URL configurada ou o ambiente foi forçado para fora de tst;
    # testes de banco falham sem URL (fixture `url_tst`).
    if os.environ.get(VAR_URL_TST) or os.environ.get("ABAKO_ENV", "tst") != "tst":
        try:
            verificar_ambiente_tst()
        except AlvoInvalido as exc:
            pytest.exit(f"ABORTADO: alvo do banco não é `tst`: {exc}", returncode=2)
