"""Decisão de alvo das migrações (ADR 019/025): puro, sem conectar em nenhum banco."""

from __future__ import annotations

import os
from pathlib import Path

import pytest

from db.alvo import AlvoInvalido, carregar_env, decidir_alvo, verificar_url_prd

URL_PRD = "postgresql://u:p@127.0.0.1:5433/prd"
URL_TST = "postgresql://u:p@127.0.0.1:5433/tst"


def test_padrao_e_tst() -> None:
    assert decidir_alvo({"ABAKO_DB_MIGRATE_URL_TST": URL_TST}) == ("tst", URL_TST)


def test_prd_sem_confirmacao_recusa() -> None:
    env = {"ABAKO_ENV": "prd", "ABAKO_DB_MIGRATE_URL_PRD": URL_PRD}
    with pytest.raises(AlvoInvalido, match="confirmação"):
        decidir_alvo(env)


def test_prd_confirmado_aceita() -> None:
    env = {"ABAKO_ENV": "prd", "ABAKO_CONFIRMA_PRD": "sim", "ABAKO_DB_MIGRATE_URL_PRD": URL_PRD}
    assert decidir_alvo(env) == ("prd", URL_PRD)


@pytest.mark.parametrize(
    "url",
    [
        "",
        "postgresql://u:p@127.0.0.1:5433/tst",
        "postgresql://u:p@127.0.0.1:5432/prd",
        "postgresql://u:p@db.exemplo.com:5433/prd",
        "postgresql://u:p@127.0.0.1:5433/prd?host=outro",
    ],
)
def test_url_prd_invalida(url: str) -> None:
    with pytest.raises(AlvoInvalido):
        verificar_url_prd(url)
    env = {"ABAKO_ENV": "prd", "ABAKO_CONFIRMA_PRD": "sim", "ABAKO_DB_MIGRATE_URL_PRD": url}
    with pytest.raises(AlvoInvalido):
        decidir_alvo(env)


def test_env_invalido() -> None:
    with pytest.raises(AlvoInvalido):
        decidir_alvo({"ABAKO_ENV": "dev"})


def test_confirmacao_nao_vem_do_arquivo_env(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.delenv("ABAKO_CONFIRMA_PRD", raising=False)
    monkeypatch.delenv("ABAKO_TESTE_OUTRA", raising=False)
    arq = tmp_path / ".env"
    arq.write_text("ABAKO_CONFIRMA_PRD=sim\nABAKO_TESTE_OUTRA=ok\n", encoding="utf-8")
    carregar_env(arq)
    assert "ABAKO_CONFIRMA_PRD" not in os.environ
    assert os.environ["ABAKO_TESTE_OUTRA"] == "ok"
    monkeypatch.delenv("ABAKO_TESTE_OUTRA", raising=False)
