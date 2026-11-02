"""Cria o banco descartável `restauracao` e seu dono (passo de ADMIN, idempotente, ADR 037).

Para volumes já existentes (o `initdb/02-restauracao.sh` só roda num volume novo). Nunca apaga
nada: se o banco já existe, só confere a senha do dono. Para deixá-lo vazio de novo, o USUÁRIO
o remove por conta própria (o guardrail de `dropdb` dos agentes não ganha exceção, ADR 032) e
roda este script outra vez. Senha do dono: `ABAKO_OWNER_RESTAURACAO_PASSWORD` (.env); senha de
admin: arquivo `ABAKO_ADMIN_PASSWORD_FILE`. Uso: `python -m scripts.criar_descartavel`.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

import psycopg
from psycopg import sql

from db.alvo import BANCO_RESTAURACAO, PORTA_ABAKO, USUARIO_RESTAURACAO, carregar_env

VAR_SENHA = "ABAKO_OWNER_RESTAURACAO_PASSWORD"
VAR_ARQ_ADMIN = "ABAKO_ADMIN_PASSWORD_FILE"
VAR_USUARIO_ADMIN = "ABAKO_ADMIN_USER"


def _exigir(var: str) -> str:
    valor = os.environ.get(var, "")
    if not valor:
        raise SystemExit(f"{var} não definida (ver .env.example)")
    return valor


def main() -> int:
    carregar_env()
    senha = _exigir(VAR_SENHA)
    senha_admin = Path(_exigir(VAR_ARQ_ADMIN)).read_text(encoding="utf-8").strip()
    papel = sql.Identifier(USUARIO_RESTAURACAO)
    atributos = sql.SQL(" LOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE PASSWORD {}").format(
        sql.Literal(senha)
    )
    with psycopg.connect(
        host="127.0.0.1",
        port=PORTA_ABAKO,
        dbname="postgres",
        user=os.environ.get(VAR_USUARIO_ADMIN) or "abako_admin",
        password=senha_admin,
        autocommit=True,  # CREATE DATABASE não roda dentro de transação
    ) as conn:
        existe = conn.execute(
            "SELECT 1 FROM pg_roles WHERE rolname = %s", (USUARIO_RESTAURACAO,)
        ).fetchone()
        verbo = "ALTER ROLE " if existe else "CREATE ROLE "
        conn.execute(sql.SQL(verbo) + papel + atributos)
        print(f"papel {USUARIO_RESTAURACAO}: {'atualizado' if existe else 'criado'}")
        dono = conn.execute(
            "SELECT pg_get_userbyid(datdba) FROM pg_database WHERE datname = %s",
            (BANCO_RESTAURACAO,),
        ).fetchone()
        if dono is not None:
            if dono[0] != USUARIO_RESTAURACAO:
                print(
                    f"ERRO: banco {BANCO_RESTAURACAO} já existe com dono {dono[0]!r}, "
                    f"esperado {USUARIO_RESTAURACAO!r}. Não é o descartável deste script; "
                    "confira e recrie-o você mesmo antes de restaurar.",
                    file=sys.stderr,
                )
                return 2
            print(f"banco {BANCO_RESTAURACAO}: já existe com o dono certo (nada alterado)")
            return 0
        banco = sql.Identifier(BANCO_RESTAURACAO)
        conn.execute(sql.SQL("CREATE DATABASE {} OWNER {}").format(banco, papel))
        conn.execute(sql.SQL("REVOKE ALL ON DATABASE {} FROM PUBLIC").format(banco))
        print(f"banco {BANCO_RESTAURACAO}: criado (vazio)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
