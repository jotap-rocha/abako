"""Cria os papéis `abako_app` e `abako_pipeline` no cluster (ou atualiza suas senhas).

Papéis são do cluster, compartilhados por `tst` e `prd`; o dono do banco não tem CREATEROLE,
então este passo é de ADMIN e roda uma vez, pelo usuário, antes das migrações da task 03.
Senhas vêm do ambiente (`ABAKO_APP_PASSWORD`, `ABAKO_PIPELINE_PASSWORD`, via .env); a senha de
admin vem do arquivo apontado por `ABAKO_ADMIN_PASSWORD_FILE` (fora do repositório). Nada é
impresso além dos nomes dos papéis. O usuário admin é `abako_admin`, ou o de
`ABAKO_ADMIN_USER` (o CI usa o superusuário do Postgres efêmero). Uso: `python -m scripts.criar_papeis`.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

import psycopg
from psycopg import sql

from db.alvo import PORTA_ABAKO, carregar_env

PAPEL_APP = "abako_app"
PAPEL_PIPELINE = "abako_pipeline"
VAR_SENHA_APP = "ABAKO_APP_PASSWORD"
VAR_SENHA_PIPELINE = "ABAKO_PIPELINE_PASSWORD"
VAR_ARQ_ADMIN = "ABAKO_ADMIN_PASSWORD_FILE"
VAR_USUARIO_ADMIN = "ABAKO_ADMIN_USER"
ADMIN_PADRAO = "abako_admin"


def comandos_papel(nome: str, senha: str, somente_leitura: bool) -> list[sql.Composed]:
    """SQL idempotente do papel: sem superuser/CREATEROLE; pipeline com transação só-leitura."""
    existe = sql.SQL("SELECT 1 FROM pg_roles WHERE rolname = {}").format(sql.Literal(nome))
    atributos = sql.SQL("LOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE PASSWORD {}").format(
        sql.Literal(senha)
    )
    return [
        existe,
        sql.SQL("CREATE ROLE {} ").format(sql.Identifier(nome)) + atributos,
        sql.SQL("ALTER ROLE {} ").format(sql.Identifier(nome)) + atributos,
        sql.SQL("ALTER ROLE {} SET default_transaction_read_only = {}").format(
            sql.Identifier(nome), sql.SQL("on" if somente_leitura else "off")
        ),
    ]


def _exigir(var: str) -> str:
    valor = os.environ.get(var, "")
    if not valor:
        raise SystemExit(f"{var} não definida (ver .env.example)")
    return valor


def main() -> int:
    carregar_env()
    senha_admin = Path(_exigir(VAR_ARQ_ADMIN)).read_text(encoding="utf-8").strip()
    papeis = [
        (PAPEL_APP, _exigir(VAR_SENHA_APP), False),
        (PAPEL_PIPELINE, _exigir(VAR_SENHA_PIPELINE), True),
    ]
    with psycopg.connect(
        host="127.0.0.1",
        port=PORTA_ABAKO,
        dbname="postgres",
        user=os.environ.get(VAR_USUARIO_ADMIN) or ADMIN_PADRAO,
        password=senha_admin,
    ) as conn:
        for nome, senha, somente_leitura in papeis:
            existe, criar, alterar, leitura = comandos_papel(nome, senha, somente_leitura)
            achou = conn.execute(existe).fetchone() is not None
            conn.execute(alterar if achou else criar)
            conn.execute(leitura)
            print(f"papel {nome}: {'atualizado' if achou else 'criado'}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
