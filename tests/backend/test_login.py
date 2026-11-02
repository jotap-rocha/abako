"""SPEC-002-AC-1: senha errada é rejeitada e o excesso de tentativas é limitado."""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from backend.seguranca import LimitadorLogin
from tests.backend.conftest import ORIGEM, Usuario, logar

pytestmark = pytest.mark.banco


def _tentar(client: TestClient, login: str, senha: str) -> int:
    r = client.post("/auth/login", json={"login": login, "senha": senha}, headers=ORIGEM)
    code: int = r.status_code
    return code


def test_rate_limit(client: TestClient, usuario: Usuario) -> None:
    # limite do fixture `settings`: 3 falhas
    for _ in range(3):
        assert _tentar(client, usuario.login, "errada") == 401
    # bloqueado: nem a senha certa passa
    r = client.post(
        "/auth/login", json={"login": usuario.login, "senha": usuario.senha}, headers=ORIGEM
    )
    assert r.status_code == 429
    assert int(r.headers["Retry-After"]) > 0
    # outro login não é afetado por esse bloqueio
    assert _tentar(client, "outro_login", "errada") == 401


def test_login_certo_e_login_inexistente(client: TestClient, usuario: Usuario) -> None:
    assert _tentar(client, "nao_existe", "qualquer") == 401
    logar(client, usuario)
    assert client.get("/auth/eu").status_code == 200


def test_sucesso_zera_falhas(client: TestClient, usuario: Usuario) -> None:
    assert _tentar(client, usuario.login, "errada") == 401
    logar(client, usuario)
    for _ in range(2):
        assert _tentar(client, usuario.login, "errada") == 401
    assert _tentar(client, usuario.login, usuario.senha) == 200


def test_janela_expira() -> None:
    t = [0.0]
    lim = LimitadorLogin(2, 60, relogio=lambda: t[0])
    lim.registrar_falha("a")
    lim.registrar_falha("a")
    assert lim.espera_s("a") > 0
    t[0] = 61.0
    assert lim.espera_s("a") == 0
