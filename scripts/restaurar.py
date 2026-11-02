"""Restauração de um backup no banco DESCARTÁVEL `restauracao` (ADR 032/037). Só o usuário roda.

Ordem das garantias:
1. O alvo é conferido ANTES de ler `.env` ou conectar: `prd`, `tst` e qualquer outro são
   recusados; só `restauracao` passa.
2. A URL `ABAKO_DB_RESTAURACAO_URL` passa pelo guarda (127.0.0.1:5433, banco `restauracao`,
   usuário `abako_owner_restauracao`) e o servidor confirma `current_database()`.
3. O banco tem de estar VAZIO. Este script nunca apaga nada (sem DROP/dropdb/--clean): para
   repetir, o usuário recria o descartável (ver `docs/operacao/backup-restore.md`).
4. A chave PRIVADA vem só do argumento `--identidade` (pendrive), nunca do `.env`.
5. `age -d | pg_restore` por pipe: o dump em claro nunca toca o disco.
Ao final imprime contagem de linhas e somas NUMERIC por tabela (sem valores individuais).

Uso: `python -m scripts.restaurar --arquivo <backup.dump.age> --identidade <chave-privada>`
"""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

import psycopg

from db.alvo import (
    BANCO_RESTAURACAO,
    VAR_URL_RESTAURACAO,
    AlvoInvalido,
    carregar_env,
    url_psycopg,
    verificar_alvo_restauracao,
    verificar_banco_conectado,
    verificar_url_restauracao,
)
from db.conteiner import (
    FalhaExterna,
    ambiente_com_senha,
    comando_no_conteiner,
    credencial,
    encadear,
    exigir_binario,
    nome_conteiner,
    pasta_fora_do_repo,
    verificar_conteiner,
)
from db.resumo import banco_vazio, formatar, resumir
from db.retencao import ler_nome

ARGS_RESTORE = ["--no-owner", "--no-privileges", "--exit-on-error", "--single-transaction"]


def _conectar_conferido(url: str) -> psycopg.Connection[tuple[object, ...]]:
    conn = psycopg.connect(url_psycopg(url))
    linha = conn.execute("SELECT current_database()").fetchone()
    verificar_banco_conectado(BANCO_RESTAURACAO, linha[0] if linha else None)
    return conn


def restaurar(alvo: str, arquivo: Path, identidade: Path) -> list[str]:
    verificar_alvo_restauracao(alvo)  # antes de qualquer leitura de ambiente ou conexão
    if ler_nome(arquivo.name) is None:
        raise AlvoInvalido("arquivo não segue o padrão abako-<amb>-AAAAMMDD-HHMMSS.dump.age")
    if not arquivo.is_file():
        raise AlvoInvalido("arquivo de backup não encontrado")
    identidade = pasta_fora_do_repo(identidade, "--identidade")
    if not identidade.is_file():
        raise AlvoInvalido("--identidade não aponta para um arquivo (pendrive conectado?)")
    carregar_env()
    url = os.environ.get(VAR_URL_RESTAURACAO, "")
    verificar_url_restauracao(url)
    age = exigir_binario("age")
    docker = exigir_binario("docker")
    conteiner = nome_conteiner(os.environ)
    verificar_conteiner(docker, conteiner)

    with _conectar_conferido(url) as conn:
        if not banco_vazio(conn):
            raise AlvoInvalido(
                f"banco {BANCO_RESTAURACAO!r} não está vazio; recrie-o antes (passo do usuário)"
            )
    cred = credencial(url)
    decifra = [age, "-d", "-i", str(identidade), str(arquivo)]
    restore = comando_no_conteiner(docker, conteiner, cred, "pg_restore", ARGS_RESTORE, stdin=True)
    encadear(decifra, restore, env_consumidor=ambiente_com_senha(cred.senha))
    with _conectar_conferido(url) as conn:
        return formatar(resumir(conn))


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description="Restaura um backup no banco descartável.")
    p.add_argument("--alvo", default=BANCO_RESTAURACAO, help="só 'restauracao' é aceito")
    p.add_argument("--arquivo", type=Path, required=True, help="backup .dump.age")
    p.add_argument("--identidade", type=Path, required=True, help="chave privada (pendrive)")
    a = p.parse_args(argv)
    try:
        linhas = restaurar(a.alvo, a.arquivo, a.identidade)
    except (AlvoInvalido, FalhaExterna) as exc:
        print(f"restauração RECUSADA/FALHOU: {exc}", file=sys.stderr)
        return 2
    print(f"restaurado em {BANCO_RESTAURACAO}. Conferência (compare com resumo_banco da origem):")
    for linha in linhas:
        print(f"  {linha}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
