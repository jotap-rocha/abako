"""Comando local de usuários (ADR 020/038): criar, redefinir senha, recusar senha fraca."""

from __future__ import annotations

import psycopg
import pytest
from fastapi.testclient import TestClient

from backend.cli import main
from tests.backend.conftest import ORIGEM, Usuario, apagar_usuarios, criar_usuario

pytestmark = pytest.mark.banco


def _senhas(monkeypatch: pytest.MonkeyPatch, senha: str, repeticao: str | None = None) -> None:
    respostas = iter([senha, senha if repeticao is None else repeticao])
    monkeypatch.setattr("backend.cli.getpass.getpass", lambda _prompt: next(respostas))


def test_criar_redefinir_e_senha_fraca(
    esquema: str, client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    ref = criar_usuario(esquema, "cli_ref")  # só para gerar um login único
    apagar_usuarios(esquema, [ref])
    login = ref.login
    try:
        _senhas(monkeypatch, "curta")
        assert main(["criar-usuario", login]) == 1
        _senhas(monkeypatch, "senha-longa-123", "diferente-123456")
        assert main(["criar-usuario", login]) == 1

        _senhas(monkeypatch, "primeira-senha-123")
        assert main(["criar-usuario", login]) == 0
        _senhas(monkeypatch, "primeira-senha-123")
        assert main(["criar-usuario", login]) == 1  # login duplicado

        corpo = {"login": login, "senha": "primeira-senha-123"}
        assert client.post("/api/auth/login", json=corpo, headers=ORIGEM).status_code == 200
        _senhas(monkeypatch, "segunda-senha-1234")
        assert main(["redefinir-senha", login]) == 0
        # a sessão aberta caiu e a senha antiga não vale mais
        assert client.get("/api/auth/eu").status_code == 401
        assert client.post("/api/auth/login", json=corpo, headers=ORIGEM).status_code == 401
        novo = {"login": login, "senha": "segunda-senha-1234"}
        assert client.post("/api/auth/login", json=novo, headers=ORIGEM).status_code == 200

        _senhas(monkeypatch, "qualquer-senha-123")
        assert main(["redefinir-senha", "nao_existe_xyz"]) == 1
    finally:
        with psycopg.connect(esquema) as conn:
            linha = conn.execute(
                "SELECT user_id FROM usuario WHERE login = %s", (login,)
            ).fetchone()
        if linha:
            apagar_usuarios(esquema, [Usuario(linha[0], login)])
