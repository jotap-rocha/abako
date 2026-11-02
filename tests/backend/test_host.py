"""SPEC-002-AC-3 (INV-34, ADR 035): só os três Host da lista são aceitos."""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

pytestmark = pytest.mark.banco


def test_host_permitido_e_invalido(client: TestClient) -> None:
    for host in ("abako.localhost:8080", "localhost:8080", "127.0.0.1:8080", "localhost"):
        r = client.get("/auth/eu", headers={"Host": host})
        assert r.status_code == 401, host  # passou do Host; falta só a sessão
    for host in ("evil.example", "abako.localhost.evil.example", "127.0.0.2:8080", "[::1]:8080"):
        r = client.get("/auth/eu", headers={"Host": host})
        assert r.status_code == 400, host


def test_cabecalhos_de_seguranca(client: TestClient) -> None:
    for r in (client.get("/auth/eu"), client.get("/auth/eu", headers={"Host": "evil.example"})):
        assert r.headers["Cache-Control"] == "no-store"
        assert "default-src 'self'" in r.headers["Content-Security-Policy"]
        assert "'unsafe-inline'" not in r.headers["Content-Security-Policy"]


def test_settings_recusa_curinga_e_origem_externa() -> None:
    from pydantic import SecretStr, ValidationError

    from backend.settings import Settings

    with pytest.raises(ValidationError):
        Settings(db_app_url=SecretStr("x"), hosts_permitidos=("*",))
    with pytest.raises(ValidationError):
        Settings(db_app_url=SecretStr("x"), origens_permitidas=("https://evil.example",))


def test_cors_so_para_origem_permitida(client: TestClient) -> None:
    pedido = {"Access-Control-Request-Method": "POST"}
    ok = client.options("/auth/login", headers={**pedido, "Origin": "http://localhost:8080"})
    assert ok.headers["access-control-allow-origin"] == "http://localhost:8080"
    ruim = client.options("/auth/login", headers={**pedido, "Origin": "http://evil.example"})
    assert "access-control-allow-origin" not in ruim.headers
