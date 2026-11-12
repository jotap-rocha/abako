"""SPA servida na mesma origem da API (ADR 035): fallback, API intacta, sem path traversal."""

from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from pydantic import SecretStr

from backend.app import criar_app
from backend.settings import Settings
from tests.backend.conftest import BASE


@pytest.fixture
def cliente_spa(tmp_path: Path) -> Iterator[TestClient]:
    dist = tmp_path / "dist"
    (dist / "assets").mkdir(parents=True)
    (dist / "index.html").write_text("<html>spa</html>", encoding="utf-8")
    (dist / "assets" / "app.js").write_text("console.log(1)", encoding="utf-8")
    (tmp_path / "segredo.txt").write_text("fora do build", encoding="utf-8")
    cfg = Settings(db_app_url=SecretStr("x"), frontend_dist=dist)
    with TestClient(criar_app(cfg), base_url=BASE) as c:
        yield c


def test_spa_serve_arquivo_e_cai_no_indice(cliente_spa: TestClient) -> None:
    assert cliente_spa.get("/assets/app.js").text == "console.log(1)"
    # rota de tela inexistente como arquivo: a SPA decide
    assert "spa" in cliente_spa.get("/saldos").text
    assert "spa" in cliente_spa.get("/").text


def test_api_desconhecida_e_404_e_nao_o_indice(cliente_spa: TestClient) -> None:
    assert cliente_spa.get("/api/nao-existe").status_code == 404
    assert cliente_spa.get("/api").status_code == 404
    assert cliente_spa.get("/api/openapi.json").status_code == 200


def test_sem_path_traversal(cliente_spa: TestClient) -> None:
    for caminho in ("/../segredo.txt", "/%2e%2e/segredo.txt", "/assets/../../segredo.txt"):
        assert "fora do build" not in cliente_spa.get(caminho).text, caminho


def test_cabecalhos_tambem_no_estatico(cliente_spa: TestClient) -> None:
    r = cliente_spa.get("/")
    assert r.headers["Cache-Control"] == "no-store"
    assert "default-src 'self'" in r.headers["Content-Security-Policy"]


def test_contrato_so_tem_rotas_da_api_e_nao_a_da_spa(cliente_spa: TestClient) -> None:
    """A rota da SPA não entra no contrato: o cliente TS depende dele (SPEC-012-AC-1)."""
    caminhos = set(cliente_spa.get("/api/openapi.json").json()["paths"])
    assert caminhos == {
        "/api/auth/login",
        "/api/auth/logout",
        "/api/auth/eu",
        "/api/contas",
        "/api/contas/{conta_id}",
        "/api/contas/{conta_id}/snapshots",
        "/api/saldos",
        "/api/r4",
        "/api/lancamentos",
        "/api/lancamentos/{transacao_id}",
        "/api/lancamentos/{transacao_id}/estorno",
        "/api/pessoas",
        "/api/pessoas/a-receber",
        "/api/pessoas/{pessoa_id}",
        "/api/pessoas/{pessoa_id}/a-receber",
        "/api/gasto-real",
        "/api/receita",
        "/api/reserva",
        "/api/reserva/parametros",
        "/api/linhas-credito",
        "/api/linhas-credito/{linha_id}",
        "/api/linhas-credito/{linha_id}/limite",
        "/api/cartoes/{conta_id}/fechamentos",
        "/api/cartoes/{conta_id}/faturas/{competencia}",
    }


def test_byte_nulo_na_url_nao_vira_500_e_mantem_cabecalhos(cliente_spa: TestClient) -> None:
    for caminho in ("/%00", "/assets/%00x"):
        r = cliente_spa.get(caminho)
        assert r.status_code == 200 and "spa" in r.text, caminho
        assert r.headers["Cache-Control"] == "no-store"
        assert "default-src 'self'" in r.headers["Content-Security-Policy"]


def test_head_na_spa(cliente_spa: TestClient) -> None:
    assert cliente_spa.head("/").status_code == 200
    assert cliente_spa.head("/assets/app.js").status_code == 200
