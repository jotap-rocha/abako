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
        [{"id": "SPEC-001-AC-6", "spec": "SPEC-001", "teste": [], "waiver": "humano: link do run"}],
        ["SPEC-001"],
    )
    r = analisar(inv, crit, ent, tmp_path)
    assert r.sem_teste == [] and r.quebrados == []


def test_contratos_reais_nao_tem_quebrados() -> None:
    r = analisar()
    assert r.quebrados == []


def _um_inv(tmp: Path, item: dict[str, Any], entregues: list[str] | None = None) -> Any:
    inv, crit, ent = _contratos(tmp, [item], [], entregues or [])
    return analisar(inv, crit, ent, tmp)


def test_spec_ausente_ou_invalida_e_quebrada(tmp_path: Path) -> None:
    assert _um_inv(tmp_path, {"id": "INV-01", "teste": []}).quebrados == ["INV-01"]
    assert _um_inv(tmp_path, {"id": "INV-01", "spec": "xyz", "teste": []}).quebrados == ["INV-01"]
    r = _um_inv(tmp_path, {"id": "INV-01", "spec": "futura", "teste": []})
    assert r.pendentes == ["INV-01"] and r.quebrados == []


def _arquivo_teste(tmp: Path, corpo: str) -> None:
    (tmp / "tests").mkdir(exist_ok=True)
    (tmp / "tests" / "test_y.py").write_text(corpo, encoding="utf-8")
    (tmp / "tests" / "test_z.py").write_text("def test_so_aqui():\n    pass\n", encoding="utf-8")


def test_referencia_exige_nome_de_teste_valido(tmp_path: Path) -> None:
    _arquivo_teste(
        tmp_path,
        "import pytest\n\n"
        "def test_ok():\n    pass\n\n"
        "def auxiliar():\n    pass\n\n"
        '@pytest.mark.skip(reason="x")\ndef test_pulado():\n    pass\n\n'
        '@pytest.mark.skipif(True, reason="x")\ndef test_pulado_if():\n    pass\n\n'
        "@pytest.mark.xfail\ndef test_xfail():\n    pass\n",
    )
    ruins = [
        "tests/test_y.py",  # sem ::nome
        "tests/test_y.py::auxiliar",  # não começa com test_
        "tests/test_y.py::test_pulado",
        "tests/test_y.py::test_pulado_if",
        "tests/test_y.py::test_xfail",
        "tests/test_y.py::test_so_aqui",  # a função existe só em outro arquivo
    ]
    for ref in ruins:
        r = _um_inv(tmp_path, {"id": "INV-01", "spec": "SPEC-008", "teste": [ref]})
        assert r.quebrados == ["INV-01"], ref
    ok = _um_inv(
        tmp_path, {"id": "INV-01", "spec": "SPEC-008", "teste": ["tests/test_y.py::test_ok"]}
    )
    assert ok.quebrados == [] and ok.sem_teste == []


def test_waiver_exige_prefixo_humano_e_motivo(tmp_path: Path) -> None:
    for ruim in ["link", "humano:", "humano:   ", "Humano: x"]:
        r = _um_inv(
            tmp_path, {"id": "SPEC-001-AC-6", "spec": "SPEC-001", "teste": [], "waiver": ruim}
        )
        assert r.quebrados == ["SPEC-001-AC-6"], ruim
    ok = _um_inv(
        tmp_path,
        {"id": "SPEC-001-AC-6", "spec": "SPEC-001", "teste": [], "waiver": "humano: link pendente"},
    )
    assert ok.quebrados == [] and ok.sem_teste == []
    assert ok.waivers == {"SPEC-001-AC-6": "humano: link pendente"}


def test_waiver_junto_com_teste_invalido_quebra_e_valido_aparece(tmp_path: Path) -> None:
    ref = _teste_existente(tmp_path)
    r = _um_inv(tmp_path, {"id": "INV-01", "spec": "SPEC-008", "teste": [ref], "waiver": "x"})
    assert r.quebrados == ["INV-01"]
    r = _um_inv(
        tmp_path, {"id": "INV-01", "spec": "SPEC-008", "teste": [ref], "waiver": "humano: ok"}
    )
    assert r.quebrados == [] and "INV-01" in r.waivers


def test_waiver_ativo_listado_na_saida(tmp_path: Path, capsys: Any) -> None:
    inv, crit, ent = _contratos(
        tmp_path,
        [],
        [{"id": "SPEC-001-AC-6", "spec": "SPEC-001", "teste": [], "waiver": "humano: pendente"}],
        [],
    )
    args = ["--invariantes", str(inv), "--criterios", str(crit), "--entregues", str(ent)]
    for extra in ([], ["--estrito"]):
        assert main([*extra, *args, "--raiz", str(tmp_path)]) == 0
        assert "waiver ativo SPEC-001-AC-6" in capsys.readouterr().out


def test_specs_com_todas_as_tasks_done_estao_em_entregues(tmp_path: Path) -> None:
    from scripts.rastreabilidade import specs_completas, specs_faltando

    tasks = tmp_path / "tasks"
    tasks.mkdir()
    (tasks / "01-a.md").write_text("# SPEC-001a: a\n\n**Status:** done  \n", encoding="utf-8")
    (tasks / "02-b.md").write_text("# SPEC-001b: b\n\n**Status:** not started\n", encoding="utf-8")
    (tasks / "03-c.md").write_text("# SPEC-002: c\n\n**Status:** done\n", encoding="utf-8")
    assert specs_completas(tasks) == {"SPEC-002"}
    ent = _escreve(tmp_path / "e.yaml", {"entregues": []})
    assert specs_faltando(tasks, ent) == ["SPEC-002"]
    ent = _escreve(tmp_path / "e.yaml", {"entregues": ["SPEC-002"]})
    assert specs_faltando(tasks, ent) == []


def test_specs_entregues_do_repositorio_estao_em_dia() -> None:
    from scripts.rastreabilidade import ENTREGUES, specs_faltando

    assert specs_faltando(RAIZ / "tasks" / "abako", ENTREGUES) == []
