"""SPEC-001-AC-5: a rastreabilidade lista invariantes/critérios sem teste (ADR 021)."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml

from scripts.rastreabilidade import analisar, main

RAIZ = Path(__file__).resolve().parents[1]


def _escreve(caminho: Path, dados: object) -> Path:
    caminho.write_text(yaml.safe_dump(dados, allow_unicode=True), encoding="utf-8")
    return caminho


def _teste_existente(tmp: Path) -> str:
    (tmp / "tests").mkdir(exist_ok=True)
    (tmp / "tests" / "test_x.py").write_text("def test_ok():\n    pass\n", encoding="utf-8")
    return "tests/test_x.py::test_ok"


def _contratos(
    tmp: Path, invs: list[dict[str, Any]], crits: list[dict[str, Any]], entregues: list[str]
) -> tuple[Path, Path, Path]:
    return (
        _escreve(tmp / "inv.yaml", {"versao": 1, "invariantes": invs}),
        _escreve(tmp / "crit.yaml", {"versao": 1, "criterios": crits}),
        _escreve(tmp / "ent.yaml", {"entregues": entregues}),
    )


def test_lista_sem_teste(tmp_path: Path) -> None:
    ref = _teste_existente(tmp_path)
    inv, crit, ent = _contratos(
        tmp_path,
        [
            {"id": "INV-01", "spec": "SPEC-001", "teste": [ref]},
            {"id": "INV-02", "spec": "SPEC-001", "teste": []},
        ],
        [
            {"id": "SPEC-001-AC-1", "spec": "SPEC-001", "teste": [ref]},
            {"id": "SPEC-001-AC-2", "spec": "SPEC-001", "teste": []},
        ],
        ["SPEC-001"],
    )
    r = analisar(inv, crit, ent, tmp_path)
    assert r.sem_teste == ["INV-02", "SPEC-001-AC-2"]
    assert r.quebrados == ["INV-02", "SPEC-001-AC-2"]  # spec entregue sem teste

    # tudo coberto: lista vazia
    inv, crit, ent = _contratos(
        tmp_path,
        [{"id": "INV-01", "spec": "SPEC-001", "teste": [ref]}],
        [{"id": "SPEC-001-AC-1", "spec": "SPEC-001", "teste": [ref]}],
        ["SPEC-001"],
    )
    vazio = analisar(inv, crit, ent, tmp_path)
    assert vazio.sem_teste == [] and vazio.quebrados == [] and vazio.pendentes == []


def test_spec_nao_entregue_e_pendente_nao_quebrado(tmp_path: Path) -> None:
    inv, crit, ent = _contratos(
        tmp_path, [{"id": "INV-05", "spec": "SPEC-008", "teste": []}], [], []
    )
    r = analisar(inv, crit, ent, tmp_path)
    assert r.pendentes == ["INV-05"] and r.quebrados == []
    assert (
        main(
            [
                "--invariantes",
                str(inv),
                "--criterios",
                str(crit),
                "--entregues",
                str(ent),
                "--raiz",
                str(tmp_path),
            ]
        )
        == 0
    )
    assert (
        main(
            [
                "--estrito",
                "--invariantes",
                str(inv),
                "--criterios",
                str(crit),
                "--entregues",
                str(ent),
                "--raiz",
                str(tmp_path),
            ]
        )
        == 1
    )


def test_referencia_inexistente_e_quebrada(tmp_path: Path) -> None:
    inv, crit, ent = _contratos(
        tmp_path,
        [
            {"id": "INV-01", "spec": "SPEC-008", "teste": ["tests/nao_existe.py::test_a"]},
            {"id": "INV-02", "spec": "SPEC-008", "teste": [_teste_existente(tmp_path) + "x"]},
        ],
        [],
        [],
    )
    r = analisar(inv, crit, ent, tmp_path)
    assert r.quebrados == ["INV-01", "INV-02"]
    assert r.sem_teste == []  # declararam teste, mas ele não existe


def test_waiver_humano_conta_como_coberto(tmp_path: Path) -> None:
    inv, crit, ent = _contratos(
        tmp_path,
        [],
        [{"id": "SPEC-001-AC-6", "spec": "SPEC-001", "teste": [], "waiver": "link do run"}],
        ["SPEC-001"],
    )
    r = analisar(inv, crit, ent, tmp_path)
    assert r.sem_teste == [] and r.quebrados == []


def test_contratos_reais_nao_tem_quebrados() -> None:
    r = analisar()
    assert r.quebrados == []
