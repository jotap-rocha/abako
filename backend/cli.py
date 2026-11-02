"""Comando local de usuários: `python -m backend.cli criar-usuario|redefinir-senha LOGIN`.

Roda com o dono do banco do ambiente (ABAKO_ENV, padrão tst; prd exige a confirmação humana
de `db.alvo`). A senha é pedida sem eco e nunca é impressa nem aceita por argumento.
"""

from __future__ import annotations

import argparse
import getpass
import os
import sys

import psycopg

from backend.services.usuarios import SenhaFraca, definir_senha
from db.alvo import AlvoInvalido, carregar_env, decidir_alvo, url_psycopg, verificar_banco_conectado


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(prog="python -m backend.cli")
    p.add_argument("comando", choices=["criar-usuario", "redefinir-senha"])
    p.add_argument("login")
    a = p.parse_args(argv)
    a.login = a.login.strip().lower()  # mesma normalização do login na API
    carregar_env()
    try:
        amb, url = decidir_alvo(os.environ)
    except AlvoInvalido as exc:
        print(f"RECUSADO: {exc}", file=sys.stderr)
        return 2
    senha = getpass.getpass("Senha: ")
    if senha != getpass.getpass("Repita a senha: "):
        print("As senhas não conferem.", file=sys.stderr)
        return 1
    try:
        with psycopg.connect(url_psycopg(url)) as conn:
            banco = conn.execute("SELECT current_database()").fetchone()
            assert banco is not None
            verificar_banco_conectado(amb, banco[0])
            definir_senha(conn, a.login, senha, criar=a.comando == "criar-usuario")
    except SenhaFraca as exc:
        print(f"RECUSADO: {exc}", file=sys.stderr)
        return 1
    except LookupError as exc:
        print(f"ERRO: {exc}", file=sys.stderr)
        return 1
    except psycopg.errors.UniqueViolation:
        print("ERRO: esse login já existe.", file=sys.stderr)
        return 1
    print(f"ok: {a.comando} em {amb}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
