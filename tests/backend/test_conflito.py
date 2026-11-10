"""INV-29 / SPEC-004-AC-4: atualização com versão desatualizada → 409, sem nova versão."""

from __future__ import annotations

import psycopg
import pytest
from fastapi.testclient import TestClient

from tests.backend.conftest import Usuario, logar
from tests.backend.test_lancamentos_api import criar_conta, escrita, lancar

pytestmark = pytest.mark.banco


def _versoes(url_dono: str, user_id: int, transacao_id: int) -> int:
    with psycopg.connect(url_dono) as conn:
        linha = conn.execute(
            "SELECT count(*) FROM transacao_versao WHERE user_id = %s AND transacao_id = %s",
            (user_id, transacao_id),
        ).fetchone()
    assert linha is not None
    return int(linha[0])


def test_versao_desatualizada(client: TestClient, usuario: Usuario, esquema: str) -> None:
    csrf = logar(client, usuario)
    c = criar_conta(client, csrf, "Corrente")
    tid = lancar(client, csrf, tipo="debito", data="2026-02-02", valor="10", conta_id=c).json()[
        "transacao_id"
    ]
    edicao = {"tipo": "debito", "data": "2026-02-02", "conta_id": c}

    # Duas abas leram a versão 1; a primeira grava.
    r = client.put(
        f"/api/lancamentos/{tid}", json=edicao | {"valor": "20", "versao": 1}, headers=escrita(csrf)
    )
    assert r.status_code == 200, r.text
    assert _versoes(esquema, usuario.user_id, tid) == 2

    # A segunda aba ainda está na versão 1: conflito, nada gravado.
    r = client.put(
        f"/api/lancamentos/{tid}", json=edicao | {"valor": "30", "versao": 1}, headers=escrita(csrf)
    )
    assert r.status_code == 409
    assert "mudou desde a última leitura" in r.json()["detail"]
    r = client.delete(f"/api/lancamentos/{tid}", params={"versao": 1}, headers=escrita(csrf))
    assert r.status_code == 409
    assert _versoes(esquema, usuario.user_id, tid) == 2
    assert client.get(f"/api/lancamentos/{tid}").json()["valor"] == "20.00"
