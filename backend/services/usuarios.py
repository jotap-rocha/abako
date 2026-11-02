"""Usuários e senhas: só pelo comando local, conectado como dono do banco (ADR 020/038)."""

from __future__ import annotations

import psycopg

from backend.seguranca import hash_senha

SENHA_MINIMA = 12


class SenhaFraca(ValueError):
    """Senha abaixo do mínimo."""


def definir_senha(conn: psycopg.Connection, login: str, senha: str, *, criar: bool) -> int:
    """Cria o usuário (`criar=True`) ou troca a senha de um existente; devolve o `user_id`."""
    if len(senha) < SENHA_MINIMA:
        raise SenhaFraca(f"a senha precisa de ao menos {SENHA_MINIMA} caracteres")
    if criar:
        linha = conn.execute(
            "INSERT INTO usuario (login) VALUES (%s) RETURNING user_id", (login,)
        ).fetchone()
    else:
        linha = conn.execute("SELECT user_id FROM usuario WHERE login = %s", (login,)).fetchone()
    if linha is None:
        raise LookupError("usuário inexistente")
    user_id: int = linha[0]
    conn.execute(
        "INSERT INTO credencial (user_id, senha_hash) VALUES (%s, %s) "
        "ON CONFLICT (user_id) DO UPDATE SET senha_hash = EXCLUDED.senha_hash, "
        "atualizada_em = now()",
        (user_id, hash_senha(senha)),
    )
    if not criar:
        # Trocar a senha derruba as sessões abertas.
        conn.execute("DELETE FROM sessao WHERE user_id = %s", (user_id,))
    return user_id
