"""ADR 039: o Postgres do compose e o do CI nascem com scram em `local` e em `host`."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml

RAIZ = Path(__file__).resolve().parent.parent
ARGS = "--auth-local=scram-sha-256 --auth-host=scram-sha-256"


def _carregar(caminho: str) -> dict[str, Any]:
    dados = yaml.safe_load((RAIZ / caminho).read_text(encoding="utf-8"))
    assert isinstance(dados, dict)
    return dados


def test_compose_inicializa_com_scram() -> None:
    env = _carregar("docker-compose.yml")["services"]["postgres"]["environment"]
    assert env["POSTGRES_INITDB_ARGS"] == ARGS


def test_ci_inicializa_com_scram() -> None:
    env = _carregar(".github/workflows/ci.yml")["jobs"]["check"]["services"]["postgres"]["env"]
    assert env["POSTGRES_INITDB_ARGS"] == ARGS
