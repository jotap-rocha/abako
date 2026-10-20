"""SPEC-001-AC-4: `check` roda lint, tipos, testes e rastreabilidade e falha se uma etapa falhar."""

from __future__ import annotations

import sys

import pytest

from scripts.check import Etapa, etapas_padrao, executar, main

PY = sys.executable


def _etapa(nome: str, codigo: int) -> Etapa:
    return Etapa(nome, [PY, "-c", f"raise SystemExit({codigo})"])


def test_check_falha_quando_etapa_falha(capsys: pytest.CaptureFixture[str]) -> None:
    etapas = [_etapa("a", 0), _etapa("b", 3), _etapa("c", 0)]
    assert executar(etapas) == 1
    saida = capsys.readouterr().out
    assert "FALHOU" in saida and "b" in saida
    assert "c" in saida  # as demais etapas ainda rodam e são reportadas


def test_check_passa_quando_todas_passam() -> None:
    assert executar([_etapa("a", 0), _etapa("b", 0)]) == 0


def test_etapas_padrao_cobrem_o_contrato() -> None:
    nomes = [e.nome for e in etapas_padrao(banco="nao")]
    assert nomes == ["ruff", "mypy", "pytest (sem banco)", "contratos", "rastreabilidade"]
    com = [e.nome for e in etapas_padrao(banco="sim")]
    assert "pytest (banco)" in com


def test_com_banco_sem_contêiner_falha_explicitamente(
    capsys: pytest.CaptureFixture[str], monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr("scripts.check.banco_no_ar", lambda: False)
    assert main(["--com-banco", "--so-pre-requisitos"]) == 1
    assert "banco" in capsys.readouterr().out.lower()
