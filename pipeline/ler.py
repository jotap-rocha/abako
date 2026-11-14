"""Leitura somente leitura do arquivo analítico (ADR 008/054). Sem rota de API nem tela.

Toda consulta exige o `user_id` (INV-13): quem chama passa o da sessão. O arquivo abre com
`read_only=True`; nome de tabela vem de uma lista fixa (nunca do texto do usuário).
CLI: `python -m pipeline.ler TABELA --usuario N [--alvo tst|prd] [--destino PASTA]`.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

import duckdb

from db.alvo import carregar_env
from pipeline import esquema
from pipeline.config import ConfigInvalida, ambiente_do_processo, caminho_arquivo

LEGIVEIS = esquema.TABELAS_DE_DADOS


def consultar(arquivo: Path, tabela: str, user_id: int) -> list[dict[str, Any]]:
    """Linhas do usuário na tabela, na ordem da carga; o arquivo é aberto só para leitura."""
    if tabela not in LEGIVEIS:
        raise ValueError(f"tabela desconhecida: {tabela!r}")
    con = duckdb.connect(str(arquivo), read_only=True)
    try:
        cur = con.execute(f"SELECT * FROM {tabela} WHERE user_id = ?", [user_id])  # noqa: S608
        nomes = [d[0] for d in cur.description]
        return [dict(zip(nomes, linha, strict=True)) for linha in cur.fetchall()]
    finally:
        con.close()


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description="Lê o analítico (somente leitura).")
    p.add_argument("tabela", choices=LEGIVEIS)
    p.add_argument("--usuario", type=int, required=True)
    p.add_argument("--alvo", choices=["tst", "prd"], default="tst")
    p.add_argument("--destino", type=Path, default=None)
    a = p.parse_args(argv)
    carregar_env()
    try:
        arquivo = caminho_arquivo(ambiente_do_processo(), a.alvo, a.destino)
    except ConfigInvalida as exc:
        print(f"leitura RECUSADA: {exc}", file=sys.stderr)
        return 2
    if not arquivo.is_file():
        print("analítico ainda não gerado (rode `python -m pipeline`)", file=sys.stderr)
        return 4
    for linha in consultar(arquivo, a.tabela, a.usuario):
        print(json.dumps({k: None if v is None else str(v) for k, v in linha.items()}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
