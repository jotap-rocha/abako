"""SPEC-012-AC-1: o cliente TS é gerado do OpenAPI e a checagem falha se estiver defasado.

Duas camadas: (1) `frontend/openapi.json` tem de ser igual ao contrato atual da API;
(2) o cliente versionado em `frontend/src/api/gerado/` tem de ser igual ao que o gerador
produz a partir desse contrato. Conserto: `python -m scripts.exportar_openapi` e, em
`frontend/`, `npm run gen:api`.
"""

from __future__ import annotations

import os
import shutil
import subprocess
from pathlib import Path

from scripts.exportar_openapi import DESTINO, RAIZ, contrato_atual, serializar

FRONT = RAIZ / "frontend"
GERADO = FRONT / "src" / "api" / "gerado"


def _lf(dados: bytes) -> bytes:
    return dados.replace(b"\r\n", b"\n")


def _arquivos(pasta: Path) -> dict[str, bytes]:
    return {
        str(p.relative_to(pasta).as_posix()): _lf(p.read_bytes())
        for p in sorted(pasta.rglob("*"))
        if p.is_file()
    }


def test_cliente_atualizado(tmp_path: Path) -> None:
    versionado = _lf(DESTINO.read_bytes()).decode("utf-8")
    assert versionado == serializar(contrato_atual()), (
        "frontend/openapi.json defasado: rode `python -m scripts.exportar_openapi`"
    )

    npm = shutil.which("npm")
    assert npm is not None, "npm não encontrado no PATH (instale o Node 24 ou o 22.22+)"
    assert (FRONT / "node_modules").is_dir(), "rode `npm ci` em frontend/ antes do check"

    saida = tmp_path / "gerado"
    resultado = subprocess.run(  # noqa: S603 - comando fixo do projeto, sem entrada externa
        [npm, "run", "gen:api"],
        cwd=FRONT,
        env={**os.environ, "ABAKO_GEN_OUT": str(saida)},
        capture_output=True,
        text=True,
        timeout=120,
    )
    assert resultado.returncode == 0, resultado.stdout + resultado.stderr

    gerado_agora = _arquivos(saida)
    assert gerado_agora, "o gerador não produziu arquivos"
    assert _arquivos(GERADO) == gerado_agora, (
        "cliente TS defasado em relação ao contrato: rode `npm run gen:api` em frontend/"
    )
