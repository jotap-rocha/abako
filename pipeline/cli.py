"""CLI do pipeline: `python -m pipeline [--alvo tst|prd] [--hoje AAAA-MM-DD] [--usuario N]`.

Disparo manual. Códigos de saída: 0 ok; 2 configuração/alvo recusado; 3 outra execução em
andamento; 4 falha (o arquivo anterior fica intacto).
"""

from __future__ import annotations

import argparse
import logging
import sys
from datetime import date
from pathlib import Path

from db.alvo import carregar_env
from pipeline.config import Config, ConfigInvalida, ambiente_do_processo, montar
from pipeline.executar import RECUSADO, executar

LOG = logging.getLogger("abako.pipeline")


def construir_config(argv: list[str] | None = None) -> Config | int:
    p = argparse.ArgumentParser(description="Postgres (papel somente leitura) -> DuckDB.")
    p.add_argument("--alvo", choices=["tst", "prd"], default="tst")
    p.add_argument("--hoje", type=date.fromisoformat, default=None, help="padrão: hoje em SP")
    p.add_argument("--usuario", type=int, action="append", help="restringe a estes user_id")
    p.add_argument("--destino", type=Path, default=None, help="pasta (fora do repositório)")
    a = p.parse_args(argv)
    carregar_env()
    try:
        return montar(
            ambiente_do_processo(),
            a.alvo,
            hoje=a.hoje,
            usuarios=tuple(a.usuario) if a.usuario else None,
            diretorio=a.destino,
        )
    except ConfigInvalida as exc:
        LOG.error("pipeline RECUSADO: %s", exc)
        return RECUSADO


def main(argv: list[str] | None = None) -> int:
    logging.basicConfig(level=logging.INFO, stream=sys.stderr, format="%(levelname)s %(message)s")
    config = construir_config(argv)
    if isinstance(config, int):
        return config
    return executar(config)
