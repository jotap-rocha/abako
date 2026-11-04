"""API de contas, snapshots, saldos e R4 (SPEC-003): dinheiro como texto, isolamento, sem futuro."""

from __future__ import annotations

from collections.abc import Iterator

import psycopg
import pytest
from fastapi.testclient import TestClient

from backend.app import criar_app
from tests.backend.conftest import BASE, ORIGEM, Usuario, apagar_usuarios, criar_usuario, logar
from tests.db.util_saldo import fixture, transacao

pytestmark = pytest.mark.banco


def _escrita(csrf: str) -> dict[str, str]:
    return {**ORIGEM, "X-CSRF-Token": csrf}


def _criar_conta(client: TestClient, csrf: str, nome: str, beneficio: bool = False) -> int:
    r = client.post(
        "/api/contas", json={"nome": nome, "conta_beneficio": beneficio}, headers=_escrita(csrf)
    )
    assert r.status_code == 201, r.text
    conta_id: int = r.json()["conta_id"]
    return conta_id


def _snapshot(client: TestClient, csrf: str, conta_id: int, data: str, valor: str) -> dict:  # type: ignore[type-arg]
    r = client.post(
        f"/api/contas/{conta_id}/snapshots",
        json={"data": data, "valor": valor},
        headers=_escrita(csrf),
    )
    assert r.status_code == 201, r.text
    corpo: dict = r.json()  # type: ignore[type-arg]
    return corpo


def _lancar(url_dono: str, user_id: int, conta_id: int, data: str, valor: str) -> None:
    """Transações ainda não têm API (task 09): entram pelo dono do banco, já commitadas."""
    with psycopg.connect(url_dono) as conn:
        transacao(conn, user_id, conta_id, data, valor)


@pytest.fixture
def outro_usuario(esquema: str) -> Iterator[Usuario]:
    u = criar_usuario(esquema, "o")
    yield u
    apagar_usuarios(esquema, [u])


def test_criar_conta(client: TestClient, usuario: Usuario) -> None:
    csrf = logar(client, usuario)
    r = client.post("/api/contas", json={"nome": "  Conta Corrente  "}, headers=_escrita(csrf))
    assert r.status_code == 201
    assert r.json()["nome"] == "Conta Corrente" and r.json()["conta_beneficio"] is False
    _criar_conta(client, csrf, "Vale", beneficio=True)

    nomes = {c["nome"]: c["conta_beneficio"] for c in client.get("/api/contas").json()}
    assert nomes == {"Conta Corrente": False, "Vale": True}

    duplicada = client.post("/api/contas", json={"nome": "conta corrente"}, headers=_escrita(csrf))
    assert duplicada.status_code == 409
    for ruim in ("", "   "):
        r = client.post("/api/contas", json={"nome": ruim}, headers=_escrita(csrf))
        assert r.status_code == 422, repr(ruim)
    # escrita sem token CSRF é recusada
    assert client.post("/api/contas", json={"nome": "X"}, headers=ORIGEM).status_code == 403


def test_snapshot_saldo_e_r4_da_fixture_f_saldo_01(
    client: TestClient, usuario: Usuario, esquema: str
) -> None:
    f = fixture("F-SALDO-01")
    e = f["entrada"]
    csrf = logar(client, usuario)
    conta = _criar_conta(client, csrf, "Corrente")

    primeiro = _snapshot(client, csrf, conta, e["snapshot"]["data"], e["snapshot"]["valor"])
    assert primeiro["saldo_inicial"] is True and primeiro["divergencia"] is None
    assert primeiro["valor"] == e["snapshot"]["valor"]

    for t in e["transacoes_posteriores"]:
        _lancar(esquema, usuario.user_id, conta, t["data"], t["valor"])

    # saldo de um dia passado, vindo da API como texto
    saldo = client.get("/api/saldos", params={"em": "2026-01-12"}).json()
    assert saldo[0]["saldo"] == "1150.00" and isinstance(saldo[0]["saldo"], str)
    assert saldo[0]["snapshot_data"] == e["snapshot"]["data"]

    segundo = _snapshot(
        client, csrf, conta, e["novo_snapshot"]["data"], e["novo_snapshot"]["valor"]
    )
    assert segundo["saldo_inicial"] is False
    assert segundo["saldo_derivado"] == f["esperado"]["saldo_derivado_em_2026_01_14"]
    assert segundo["divergencia"] == f["esperado"]["divergencia"]  # derivado - snapshot

    r4 = client.get("/api/r4").json()
    assert len(r4) == 1
    assert r4[0]["conta_nome"] == "Corrente"
    assert r4[0]["divergencia"] == f["esperado"]["divergencia"]
    assert r4[0]["valor_snapshot"] == e["novo_snapshot"]["valor"]


def test_snapshot_rejeita_data_futura_e_valor_invalido(
    client: TestClient, usuario: Usuario
) -> None:
    csrf = logar(client, usuario)
    conta = _criar_conta(client, csrf, "Corrente")
    url = f"/api/contas/{conta}/snapshots"
    ruins = [
        {"data": "2999-01-01", "valor": "10.00"},  # futuro
        {"data": "2026-01-10", "valor": "abc"},
        {"data": "2026-01-10", "valor": "1.234"},  # mais de 2 casas
        {"data": "2026-01-10", "valor": 1050},  # número JSON: dinheiro é texto
        {"data": "2026-01-10", "valor": "1e3"},
        {"data": "10/01/2026", "valor": "10.00"},
    ]
    for corpo in ruins:
        r = client.post(url, json=corpo, headers=_escrita(csrf))
        assert r.status_code == 422, corpo
    assert client.get("/api/saldos", params={"em": "2999-01-01"}).status_code == 422
    assert client.get("/api/r4").json() == []  # nada foi gravado


def test_snapshot_de_conta_alheia_ou_inexistente_e_404(
    client: TestClient, usuario: Usuario, outro_usuario: Usuario, esquema: str
) -> None:
    with TestClient(criar_app(client.app.state.settings), base_url=BASE) as outro:  # type: ignore[attr-defined]
        csrf_o = logar(outro, outro_usuario)
        conta_do_outro = _criar_conta(outro, csrf_o, "Do outro")

        csrf = logar(client, usuario)
        for conta_id in (conta_do_outro, 999999999):
            r = client.post(
                f"/api/contas/{conta_id}/snapshots",
                json={"data": "2026-01-10", "valor": "10.00"},
                headers=_escrita(csrf),
            )
            assert r.status_code == 404, conta_id
        with psycopg.connect(esquema) as conn:
            linha = conn.execute(
                "SELECT count(*) FROM snapshot_saldo WHERE conta_id = %s", (conta_do_outro,)
            ).fetchone()
        assert linha is not None and linha[0] == 0


def test_saldos_e_r4_so_do_usuario_da_sessao(
    client: TestClient, usuario: Usuario, outro_usuario: Usuario
) -> None:
    with TestClient(criar_app(client.app.state.settings), base_url=BASE) as outro:  # type: ignore[attr-defined]
        csrf_o = logar(outro, outro_usuario)
        conta_o = _criar_conta(outro, csrf_o, "Do outro")
        _snapshot(outro, csrf_o, conta_o, "2026-01-10", "100.00")
        _snapshot(outro, csrf_o, conta_o, "2026-01-12", "1.00")  # R4 do outro usuário

        csrf = logar(client, usuario)
        minha = _criar_conta(client, csrf, "Minha")
        assert [s["conta_id"] for s in client.get("/api/saldos").json()] == [minha]
        assert client.get("/api/r4").json() == []
        assert len(outro.get("/api/r4").json()) == 1


def test_sem_sessao_e_401(client: TestClient) -> None:
    assert client.get("/api/saldos").status_code == 401
    assert client.get("/api/r4").status_code == 401
    assert client.post("/api/contas", json={"nome": "X"}, headers=ORIGEM).status_code == 401


def test_contrato_inclui_as_rotas_novas(client: TestClient) -> None:
    caminhos = set(client.get("/api/openapi.json").json()["paths"])
    assert {"/api/saldos", "/api/r4", "/api/contas/{conta_id}/snapshots"} <= caminhos


def test_conta_excluida_logicamente_nao_aparece_nos_saldos_nem_no_r4(
    client: TestClient, usuario: Usuario, esquema: str
) -> None:
    csrf = logar(client, usuario)
    viva = _criar_conta(client, csrf, "Viva")
    with psycopg.connect(esquema) as conn:
        linha = conn.execute(
            "INSERT INTO conta_versao (user_id, nome, excluida) VALUES (%s, 'Excluida', true) "
            "RETURNING conta_id",
            (usuario.user_id,),
        ).fetchone()
        assert linha is not None
        excluida = linha[0]
        conn.execute(
            "INSERT INTO snapshot_saldo (user_id, conta_id, data_snapshot, valor) VALUES "
            "(%s, %s, '2026-01-10', 100), (%s, %s, '2026-01-12', 1)",
            (usuario.user_id, excluida, usuario.user_id, excluida),
        )
    assert [s["conta_id"] for s in client.get("/api/saldos").json()] == [viva]
    assert client.get("/api/r4").json() == []


def test_conta_id_fora_da_faixa_e_422_e_nao_500(client: TestClient, usuario: Usuario) -> None:
    csrf = logar(client, usuario)
    for conta_id in ("99999999999999999999", "0", "-1"):
        r = client.post(
            f"/api/contas/{conta_id}/snapshots",
            json={"data": "2026-01-10", "valor": "1.00"},
            headers=_escrita(csrf),
        )
        assert r.status_code == 422, conta_id
        assert client.get(f"/api/contas/{conta_id}").status_code == 422, conta_id


def test_data_anterior_a_2000_e_recusada(client: TestClient, usuario: Usuario) -> None:
    csrf = logar(client, usuario)
    conta = _criar_conta(client, csrf, "Corrente")
    r = client.post(
        f"/api/contas/{conta}/snapshots",
        json={"data": "0001-01-01", "valor": "1.00"},
        headers=_escrita(csrf),
    )
    assert r.status_code == 422
    assert client.get("/api/saldos", params={"em": "1999-12-31"}).status_code == 422


def test_nome_duplicado_e_barrado_pelo_banco_mesmo_sem_a_checagem(
    esquema: str, usuario: Usuario
) -> None:
    """Defesa para requisições simultâneas: o índice único vale além do SELECT do service."""
    with psycopg.connect(esquema) as conn:
        conn.execute(
            "INSERT INTO conta_versao (user_id, nome) VALUES (%s, 'Mesma')", (usuario.user_id,)
        )
        with pytest.raises(psycopg.errors.UniqueViolation):
            conn.execute(
                "INSERT INTO conta_versao (user_id, nome) VALUES (%s, 'MESMA')",
                (usuario.user_id,),
            )
