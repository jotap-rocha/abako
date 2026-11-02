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
    sem = etapas_padrao(banco="nao")
    assert [e.nome for e in sem] == [
        "ruff",
        "mypy",
        "pytest (sem banco)",
        "pytest (banco)",
        "contratos",
        "rastreabilidade",
    ]
    assert [e.nome for e in sem if e.pulada] == ["pytest (banco)"]
    assert not any(e.pulada for e in etapas_padrao(banco="sim"))


def test_com_banco_sem_contêiner_falha_explicitamente(
    capsys: pytest.CaptureFixture[str], monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr("scripts.check.banco_no_ar", lambda: False)
    assert main(["--com-banco", "--so-pre-requisitos"]) == 1
    assert "banco" in capsys.readouterr().out.lower()


def test_resumo_lista_etapas_e_banco_pulado(capsys: pytest.CaptureFixture[str]) -> None:
    etapas = [_etapa("a", 0), Etapa("pytest (banco)", [], pulada=True)]
    assert executar(etapas) == 0
    saida = capsys.readouterr().out
    assert "pytest (banco): PULADO" in saida
    assert "verde parcial (banco não rodou)" in saida
    assert "check: verde\n" not in saida


def test_verde_completo_so_sem_etapas_puladas(capsys: pytest.CaptureFixture[str]) -> None:
    assert executar([_etapa("a", 0)]) == 0
    assert "check: verde\n" in capsys.readouterr().out


def test_banco_fora_do_ar_gera_resumo_parcial(
    capsys: pytest.CaptureFixture[str], monkeypatch: pytest.MonkeyPatch
) -> None:
    # simula a ausência de resposta na porta (nenhum mock de banco)
    monkeypatch.setattr("scripts.check.banco_no_ar", lambda: False)
    monkeypatch.setattr(
        "scripts.check.etapas_padrao",
        lambda banco, estrito: [
            Etapa("ruff", [PY, "-c", "pass"]),
            Etapa("pytest (banco)", [], pulada=banco != "sim"),
        ],
    )
    assert main([]) == 0
    saida = capsys.readouterr().out
    assert "pytest (banco): PULADO" in saida and "verde parcial" in saida
