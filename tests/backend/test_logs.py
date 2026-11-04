"""SPEC-002-AC-5: senha e sessão nunca aparecem em log."""

from __future__ import annotations

import logging

import psycopg
import pytest
from fastapi.testclient import TestClient

from tests.backend.conftest import BASE, ORIGEM, Usuario

pytestmark = pytest.mark.banco


def test_sem_segredo_em_log(
    client: TestClient, usuario: Usuario, caplog: pytest.LogCaptureFixture, esquema: str
) -> None:
    senha_errada = "senha-errada-xyz-987"
    with caplog.at_level(logging.DEBUG):
        client.post(
            "/api/auth/login", json={"login": usuario.login, "senha": senha_errada}, headers=ORIGEM
        )
        r = client.post(
            "/api/auth/login", json={"login": usuario.login, "senha": usuario.senha}, headers=ORIGEM
        )
        csrf = r.json()["csrf_token"]
        cookie = client.cookies["abako_sessao"]
        client.get("/api/contas")
        client.post("/api/auth/logout", headers={"Origin": BASE, "X-CSRF-Token": csrf})
        # força bloqueio para exercitar o log do 429
        for _ in range(4):  # limite 3: a quarta já encontra o bloqueio
            bloqueio = client.post(
                "/api/auth/login",
                json={"login": usuario.login, "senha": senha_errada},
                headers=ORIGEM,
            )
        assert bloqueio.status_code == 429

    registro = "\n".join(
        f"{rec.getMessage()} {rec.args!r} {rec.exc_text or ''}" for rec in caplog.records
    )
    assert "abako.auth" in {rec.name for rec in caplog.records}  # o teste capturou algo
    with psycopg.connect(esquema) as conn:
        hash_senha = conn.execute(
            "SELECT senha_hash FROM credencial WHERE user_id = %s", (usuario.user_id,)
        ).fetchone()
    assert hash_senha is not None
    for segredo in (usuario.senha, senha_errada, cookie, csrf, hash_senha[0]):
        assert segredo not in registro


def test_token_nao_fica_em_claro_no_banco(
    client: TestClient, usuario: Usuario, esquema: str
) -> None:
    r = client.post(
        "/api/auth/login", json={"login": usuario.login, "senha": usuario.senha}, headers=ORIGEM
    )
    assert r.status_code == 200
    token = client.cookies["abako_sessao"]
    with psycopg.connect(esquema) as conn:
        linhas = conn.execute(
            "SELECT token_hash FROM sessao WHERE user_id = %s", (usuario.user_id,)
        ).fetchall()
    assert len(linhas) == 1
    assert token.encode() not in bytes(linhas[0][0])
