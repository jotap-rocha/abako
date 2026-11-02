"""SPEC-002-AC-4: escrita sem token CSRF ou com Origin inválida é rejeitada."""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from tests.backend.conftest import BASE, ORIGEM, Usuario, logar

pytestmark = pytest.mark.banco


def test_csrf_e_origin(client: TestClient, usuario: Usuario) -> None:
    csrf = logar(client, usuario)
    cookie = client.cookies["abako_sessao"]

    # sem token / token errado
    assert client.post("/auth/logout", headers=ORIGEM).status_code == 403
    assert client.post("/auth/logout", headers={**ORIGEM, "X-CSRF-Token": "x"}).status_code == 403
    # Origin ausente, de outro site ou com porta/esquema diferentes
    cabecalho = {"X-CSRF-Token": csrf}
    assert client.post("/auth/logout", headers=cabecalho).status_code == 403
    for origem in ("http://evil.example", "http://127.0.0.1:9999", "https://127.0.0.1:8080"):
        r = client.post("/auth/logout", headers={**cabecalho, "Origin": origem})
        assert r.status_code == 403, origem
    # a sessão continua viva depois das recusas
    assert client.get("/auth/eu").status_code == 200

    # token e Origin corretos
    assert client.post("/auth/logout", headers={**cabecalho, "Origin": BASE}).status_code == 204
    assert client.get("/auth/eu").status_code == 401
    # a sessão morreu no servidor: reenviar o cookie antigo não vale
    client.cookies.set("abako_sessao", cookie)
    assert client.get("/auth/eu").status_code == 401


def test_login_tambem_exige_origin(client: TestClient, usuario: Usuario) -> None:
    corpo = {"login": usuario.login, "senha": usuario.senha}
    assert client.post("/auth/login", json=corpo).status_code == 403
    assert (
        client.post(
            "/auth/login", json=corpo, headers={"Origin": "http://evil.example"}
        ).status_code
        == 403
    )


def test_cookie_de_sessao(client: TestClient, usuario: Usuario) -> None:
    r = client.post(
        "/auth/login", json={"login": usuario.login, "senha": usuario.senha}, headers=ORIGEM
    )
    cookie = r.headers["set-cookie"].lower()
    assert "httponly" in cookie and "samesite=strict" in cookie
