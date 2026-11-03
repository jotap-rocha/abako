"""Regressão: `evidencias_ref` relativo à raiz do repositório é aceito (chore evidence-gate-ref).

O gate resolvia o ref contra `metrics/`, então `.claude/...` gravado a partir da raiz
(tasks 3, 4, 5) falhava como "arquivo inexistente".
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from config.evidence_gate.check import _check_evidencias_ref


def _montar(raiz: Path, ref: str) -> tuple[Path, Path]:
    manifesto = raiz / ".claude" / "evidencias" / "tasks" / "7.yaml"
    manifesto.parent.mkdir(parents=True)
    manifesto.write_text("task_id: '7'\n", encoding="utf-8")
    entregas = raiz / "metrics" / "entregas.jsonl"
    entregas.parent.mkdir()
    entregas.write_text(json.dumps({"issue": 7, "evidencias_ref": ref}) + "\n", encoding="utf-8")
    return entregas, manifesto


def _erros(entregas: Path, manifesto: Path) -> list[str]:
    return _check_evidencias_ref(
        entregas_path=entregas,
        issue=7,
        expected_manifest=manifesto,
        ref_base=entregas.parent,
    )


def test_ref_a_partir_da_raiz(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    entregas, manifesto = _montar(tmp_path, ".claude/evidencias/tasks/7.yaml")
    monkeypatch.chdir(tmp_path)
    assert _erros(entregas, manifesto) == []


def test_ref_legado_relativo_a_metrics(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    entregas, manifesto = _montar(tmp_path, "../.claude/evidencias/tasks/7.yaml")
    monkeypatch.chdir(tmp_path)
    assert _erros(entregas, manifesto) == []


def test_ref_inexistente_continua_quebrado(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    entregas, manifesto = _montar(tmp_path, ".claude/evidencias/tasks/99.yaml")
    monkeypatch.chdir(tmp_path)
    erros = _erros(entregas, manifesto)
    assert len(erros) == 1 and "quebrado" in erros[0]


def test_ref_de_outra_task_e_recusado(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    entregas, manifesto = _montar(tmp_path, ".claude/evidencias/tasks/7.yaml")
    outro = manifesto.with_name("8.yaml")
    outro.write_text("task_id: '8'\n", encoding="utf-8")
    entregas.write_text(
        json.dumps({"issue": 7, "evidencias_ref": ".claude/evidencias/tasks/8.yaml"}) + "\n",
        encoding="utf-8",
    )
    monkeypatch.chdir(tmp_path)
    erros = _erros(entregas, manifesto)
    assert len(erros) == 1 and "esperado manifesto" in erros[0]
