"""Resumo de conferência da ORIGEM do backup (contagem e somas por tabela, só agregados).

Compare com o que `scripts.restaurar` imprime (SPEC-001-AC-14). Alvo padrão `tst`; `prd` só
com `ABAKO_CONFIRMA_PRD=sim` no ambiente real (mesmo guarda das migrações). A conexão é
somente leitura desde antes do primeiro comando (`db.resumo.conectar_somente_leitura`).
Uso: `python -m scripts.resumo_banco [--alvo tst|prd]` (rodado pelo usuário).
"""

from __future__ import annotations

import argparse
import os
import sys

from db.alvo import AlvoInvalido, carregar_env, decidir_alvo, url_psycopg, verificar_banco_conectado
from db.resumo import conectar_somente_leitura, formatar, resumir


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description="Contagem e somas por tabela (só leitura).")
    p.add_argument("--alvo", choices=["tst", "prd"], default="tst")
    a = p.parse_args(argv)
    carregar_env()
    try:
        ambiente, url = decidir_alvo({**os.environ, "ABAKO_ENV": a.alvo})
    except AlvoInvalido as exc:
        print(f"resumo RECUSADO: {exc}", file=sys.stderr)
        return 2
    with conectar_somente_leitura(url_psycopg(url)) as conn:
        linha = conn.execute("SELECT current_database()").fetchone()
        verificar_banco_conectado(ambiente, linha[0] if linha else None)
        for texto in formatar(resumir(conn)):
            print(f"  {texto}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
