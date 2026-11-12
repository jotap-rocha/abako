"""API de recorrentes, ocorrências e vínculo (SPEC-010, ADR 048). Valores esperados vêm de
F-R2-04, F-R2-10 e F-R2-11 (calculados à mão); dinheiro é texto; o nome do recorrente nunca vai a
log nem a erro; `hoje` é a data civil de São Paulo, injetada de forma determinística."""

from __future__ import annotations

import logging
from collections.abc import Iterator
from datetime import UTC, datetime
from typing import Any
from urllib.parse import quote

import pytest
from fastapi.testclient import TestClient

from backend.services import gasto_real as svc_data
from tests.backend.conftest import ORIGEM, Usuario, apagar_usuarios, criar_usuario, logar
from tests.backend.util_r2_api import Cenario, escrita, hoje_em

pytestmark = pytest.mark.banco


@pytest.fixture
def outro_usuario(esquema: str) -> Iterator[Usuario]:
    u = criar_usuario(esquema, "o")
    yield u
    apagar_usuarios(esquema, [u])


def ocorrencias(client: TestClient, mes: str | None = None) -> list[dict[str, Any]]:
    r = client.get("/api/recorrentes/ocorrencias", params={} if mes is None else {"mes": mes})
    assert r.status_code == 200, r.text
    lista: list[dict[str, Any]] = r.json()
    return lista


# ------------------------------------------------------------------ cadastro e versionamento


def test_criar_listar_obter_e_texto_com_duas_casas(client: TestClient, usuario: Usuario) -> None:
    """SPEC-010-AC-13: cria (nome aparado, valor com 2 casas em texto), lista e obtém."""
    c = Cenario(client, usuario)
    r = client.post(
        "/api/recorrentes",
        json=c.corpo("  Aluguel ", valor="1500.5", dia=5, fim="2026-12"),
        headers=escrita(c.csrf),
    )
    assert r.status_code == 201, r.text
    criado = r.json()
    assert criado | {"recorrente_id": 0} == {
        "recorrente_id": 0,
        "nome": "Aluguel",
        "tipo": "fixo",
        "valor": "1500.50",
        "dia": 5,
        "conta_id": c.corrente,
        "mes_inicio": "2026-05",
        "mes_fim": "2026-12",
        "versao": 1,
    }
    c.recorrente("Salario", tipo="receita", valor="3000", dia=20)
    nomes = [x["nome"] for x in client.get("/api/recorrentes").json()]
    assert nomes == ["Aluguel", "Salario"]
    r = client.get(f"/api/recorrentes/{criado['recorrente_id']}")
    assert r.status_code == 200 and r.json() == criado


def test_editar_cria_versao_e_exige_a_versao_lida(client: TestClient, usuario: Usuario) -> None:
    """SPEC-010-AC-13: editar com a versão lida cria a versão 2; a versão antiga volta 409/AB409."""
    c = Cenario(client, usuario)
    rec = c.recorrente("Aluguel", valor="500.00")
    url = f"/api/recorrentes/{rec['recorrente_id']}"
    corpo = c.corpo("Aluguel", valor="600.00") | {"versao": 1}
    r = client.put(url, json=corpo, headers=escrita(c.csrf))
    assert r.status_code == 200, r.text
    assert (r.json()["versao"], r.json()["valor"]) == (2, "600.00")
    r = client.put(url, json=corpo, headers=escrita(c.csrf))
    assert r.status_code == 409 and r.headers["X-Abako-Erro"] == "AB409"
    assert client.get(url).json()["valor"] == "600.00"


def test_nome_repetido_e_409_ab410(client: TestClient, usuario: Usuario) -> None:
    """SPEC-010-AC-13: nome único entre os vigentes (sem diferenciar maiúsculas) é 409/AB410."""
    c = Cenario(client, usuario)
    c.recorrente("Aluguel")
    r = client.post("/api/recorrentes", json=c.corpo("ALUGUEL"), headers=escrita(c.csrf))
    assert r.status_code == 409 and r.headers["X-Abako-Erro"] == "AB410"
    assert "ALUGUEL" not in r.text


def test_excluir_e_logico_com_versao(client: TestClient, usuario: Usuario) -> None:
    """SPEC-010-AC-13: excluir exige a versão lida (409), vira 204, some das leituras (404) e
    libera o nome; excluir de novo é 404."""
    c = Cenario(client, usuario)
    rec = c.recorrente("Aluguel")
    url = f"/api/recorrentes/{rec['recorrente_id']}"
    r = client.delete(url, params={"versao": 7}, headers=escrita(c.csrf))
    assert r.status_code == 409 and r.headers["X-Abako-Erro"] == "AB409"
    r = client.delete(url, params={"versao": 1}, headers=escrita(c.csrf))
    assert r.status_code == 204
    assert client.get(url).status_code == 404
    assert client.get("/api/recorrentes").json() == []
    assert ocorrencias(client, "2026-05") == []
    r = client.delete(url, params={"versao": 2}, headers=escrita(c.csrf))
    assert r.status_code == 404 and r.headers["X-Abako-Erro"] == "AB404"
    c.recorrente("Aluguel")  # o nome volta a ficar livre


def test_regras_de_cadastro_do_banco(client: TestClient, usuario: Usuario) -> None:
    """SPEC-010-AC-13: valor zero, dia, período e conta que não é corrente são AB422; conta
    inexistente é AB404; a recusa não deixa a conexão inutilizável."""
    c = Cenario(client, usuario)
    reserva = c.conta("Reserva", "reserva", conta_mae_id=c.corrente)
    casos: list[tuple[dict[str, Any], int, str]] = [
        ({"valor": "0"}, 422, "AB422"),
        ({"dia": 0}, 422, "AB422"),
        ({"dia": 32}, 422, "AB422"),
        ({"inicio": "2026-13"}, 422, "AB422"),
        ({"inicio": "ontem"}, 422, "AB422"),
        ({"fim": "2026-04"}, 422, "AB422"),  # fim antes do início (2026-05)
        ({"conta": reserva}, 422, "AB422"),
        ({"conta": 999_999_999}, 404, "AB404"),
    ]
    for campos, status, codigo in casos:
        r = client.post(
            "/api/recorrentes", json=c.corpo("Nome-x", **campos), headers=escrita(c.csrf)
        )
        assert r.status_code == status, (campos, r.text)
        assert r.headers["X-Abako-Erro"] == codigo, campos
        assert isinstance(r.json()["detail"], str)
        assert "Nome-x" not in r.text
    assert client.get("/api/recorrentes").json() == []
    c.recorrente("Nome-x")  # depois de tudo recusado, a escrita volta a funcionar


def test_corpo_invalido_e_422_sem_eco(client: TestClient, usuario: Usuario) -> None:
    """SPEC-010-AC-13: corpo mal formado (float, tipo, chave desconhecida, versão acima do teto)
    é 422 e o nome e o valor recebidos não voltam na resposta."""
    c = Cenario(client, usuario)
    base = c.corpo("Sigiloso-ZZ")
    ruins = [
        base | {"valor": "10.123"},
        base | {"valor": "abc"},
        base | {"valor": "1000000000000"},
        base | {"valor": 10.5},
        base | {"tipo": "outro"},
        base | {"dia": "cinco"},
        base | {"extra": "Sigiloso-ZZ"},
        {k: v for k, v in base.items() if k != "conta_id"},
        base | {"nome": ""},
        base | {"nome": "x" * 81},
    ]
    for corpo in ruins:
        r = client.post("/api/recorrentes", json=corpo, headers=escrita(c.csrf))
        assert r.status_code == 422, (corpo, r.text)
        assert all("input" not in erro for erro in r.json()["detail"])
        assert "Sigiloso-ZZ" not in r.text and "10.123" not in r.text and "abc" not in r.text
    rec = c.recorrente("Aluguel")
    url = f"/api/recorrentes/{rec['recorrente_id']}"
    edicao = c.corpo("Aluguel")
    # O teto de `versao` é o do integer do banco: acima dele 422 (nunca 500); no teto, 409.
    r = client.put(url, json=edicao | {"versao": 2**31}, headers=escrita(c.csrf))
    assert r.status_code == 422
    r = client.put(url, json=edicao | {"versao": 2**31 - 1}, headers=escrita(c.csrf))
    assert r.status_code == 409
    r = client.delete(url, params={"versao": 2**31}, headers=escrita(c.csrf))
    assert r.status_code == 422
    r = client.delete(url, params={"versao": 2**31 - 1}, headers=escrita(c.csrf))
    assert r.status_code == 409
    assert client.get("/api/recorrentes/0").status_code == 422
    assert client.get(f"/api/recorrentes/{2**63}").status_code == 422


def test_user_id_no_corpo_e_descartado(
    client: TestClient, usuario: Usuario, outro_usuario: Usuario
) -> None:
    """SPEC-010-AC-13 (INV-13): `user_id` no corpo não grava para o outro usuário."""
    c = Cenario(client, usuario)
    r = client.post(
        "/api/recorrentes",
        json=c.corpo("Aluguel") | {"user_id": outro_usuario.user_id},
        headers=escrita(c.csrf),
    )
    assert r.status_code == 201, r.text
    client.post("/api/auth/logout", headers=escrita(c.csrf))
    client.cookies.clear()
    logar(client, outro_usuario)
    assert client.get("/api/recorrentes").json() == []


# ------------------------------------------------------------------ ocorrências


def test_ocorrencias_dia_29_a_31_f_r2_10(client: TestClient, usuario: Usuario) -> None:
    """SPEC-010-AC-5 e AC-13 (F-R2-10): a data é o último dia válido do mês."""
    c = Cenario(client, usuario)
    for dia in (29, 30, 31):
        c.recorrente(f"dia_{dia}", dia=dia, inicio="2026-01")
    esperado = {
        "2026-01": ["2026-01-29", "2026-01-30", "2026-01-31"],
        "2026-02": ["2026-02-28", "2026-02-28", "2026-02-28"],
        "2026-03": ["2026-03-29", "2026-03-30", "2026-03-31"],
        "2026-04": ["2026-04-29", "2026-04-30", "2026-04-30"],
        "2028-02": ["2028-02-29", "2028-02-29", "2028-02-29"],
    }
    for mes, datas in esperado.items():
        lista = ocorrencias(client, mes)
        assert [o["data"] for o in lista] == datas, mes
        assert {o["mes"] for o in lista} == {mes}


def test_ocorrencias_so_no_periodo_e_valores_em_texto(client: TestClient, usuario: Usuario) -> None:
    """SPEC-010-AC-13: só os recorrentes com o mês dentro do período (inclusive nas pontas);
    valor esperado e valor em texto com 2 casas; sem vínculo, valor = esperado."""
    c = Cenario(client, usuario)
    c.recorrente("Curto", valor="12.5", dia=3, inicio="2026-05", fim="2026-06")
    c.recorrente("Aberto", valor="40.00", dia=9, inicio="2026-06")
    assert [o["nome"] for o in ocorrencias(client, "2026-04")] == []
    assert [o["nome"] for o in ocorrencias(client, "2026-05")] == ["Curto"]
    assert [o["nome"] for o in ocorrencias(client, "2026-06")] == ["Curto", "Aberto"]
    assert [o["nome"] for o in ocorrencias(client, "2026-07")] == ["Aberto"]
    curto = ocorrencias(client, "2026-05")[0]
    assert (curto["valor_esperado"], curto["valor"], curto["vinculada"]) == (
        "12.50",
        "12.50",
        False,
    )
    assert curto["transacao_id"] is None and curto["data"] == "2026-05-03"


@pytest.mark.parametrize("mes", ["2026-13", "2026-1", "abc", "1999-12", "2026-05-01"])
def test_mes_invalido_e_ab422(client: TestClient, usuario: Usuario, mes: str) -> None:
    """SPEC-010-AC-13: o formato do mês é do banco: 422 com X-Abako-Erro: AB422, sem eco."""
    logar(client, usuario)
    r = client.get("/api/recorrentes/ocorrencias", params={"mes": mes})
    assert r.status_code == 422 and r.headers["X-Abako-Erro"] == "AB422"
    assert isinstance(r.json()["detail"], str)


def test_mes_padrao_e_o_corrente_de_sao_paulo(
    client: TestClient, usuario: Usuario, monkeypatch: pytest.MonkeyPatch
) -> None:
    """SPEC-010-AC-13: sem `mes`, vale o mês corrente em America/Sao_Paulo (virada de ano)."""
    c = Cenario(client, usuario)
    c.recorrente("Aluguel", dia=31, inicio="2026-12")

    class RelogioFalso(datetime):
        instante = datetime(2027, 1, 1, 2, 30, tzinfo=UTC)  # 31/12 23:30 em São Paulo

        @classmethod
        def now(cls, tz: Any = None) -> RelogioFalso:
            return cls.fromtimestamp(cls.instante.timestamp(), tz)

    monkeypatch.setattr(svc_data, "datetime", RelogioFalso)
    lista = ocorrencias(client)
    assert [(o["mes"], o["data"]) for o in lista] == [("2026-12", "2026-12-31")]
    RelogioFalso.instante = datetime(2027, 1, 1, 3, 30, tzinfo=UTC)  # 01/01 00:30 em São Paulo
    lista = ocorrencias(client)  # sem fim, o recorrente segue em janeiro de 2027
    assert [(o["mes"], o["data"]) for o in lista] == [("2027-01", "2027-01-31")]


def test_hoje_nao_vem_do_cliente(client: TestClient, usuario: Usuario) -> None:
    """SPEC-010-AC-13: `hoje` e `user_id` na query são ignorados."""
    c = Cenario(client, usuario)
    c.recorrente("Aluguel", inicio="2026-05")
    with hoje_em(client, "2026-05-10"):
        r = client.get("/api/recorrentes/ocorrencias", params={"hoje": "1999-01-01", "user_id": 1})
    assert r.status_code == 200 and [o["mes"] for o in r.json()] == ["2026-05"]


# ------------------------------------------------------------------ vínculo (F-R2-11)


def test_vinculo_valor_e_historico_f_r2_11(client: TestClient, usuario: Usuario) -> None:
    """SPEC-010-AC-4 e AC-13 (F-R2-11): fixo de 500,00 dia 5; débito de 480,00. Sem vínculo vale
    o esperado; vinculada vale 480,00; desvincular devolve 500,00; vincular de novo repete."""
    c = Cenario(client, usuario)
    rec = c.recorrente("Fixo", valor="500.00", dia=5, inicio="2026-05")
    rid = rec["recorrente_id"]
    t = c.debito("2026-05-06", "480.00")
    antes = ocorrencias(client, "2026-05")[0]
    assert (antes["data"], antes["valor"], antes["vinculada"]) == ("2026-05-05", "500.00", False)

    r = c.vincular(rid, "2026-05", t["transacao_id"])
    assert r.status_code == 200, r.text
    assert r.json() == {
        "recorrente_id": rid,
        "nome": "Fixo",
        "tipo": "fixo",
        "conta_id": c.corrente,
        "mes": "2026-05",
        "data": "2026-05-05",
        "valor_esperado": "500.00",
        "valor": "480.00",
        "transacao_id": t["transacao_id"],
        "vinculada": True,
    }
    assert c.vincular(rid, "2026-05", t["transacao_id"]).status_code == 200  # idempotente
    assert ocorrencias(client, "2026-05")[0]["valor"] == "480.00"

    r = c.desvincular(rid, "2026-05")
    assert r.status_code == 200, r.text
    assert (r.json()["valor"], r.json()["vinculada"], r.json()["transacao_id"]) == (
        "500.00",
        False,
        None,
    )
    # A mesma transação pode ligar de novo depois de desvinculada.
    assert c.vincular(rid, "2026-05", t["transacao_id"]).json()["valor"] == "480.00"


def test_transacao_excluida_devolve_a_ocorrencia(client: TestClient, usuario: Usuario) -> None:
    """SPEC-010-AC-4 e AC-13: excluir a transação vinculada devolve a ocorrência a pendente."""
    c = Cenario(client, usuario)
    rid = c.recorrente("Fixo", valor="500.00")["recorrente_id"]
    t = c.debito("2026-05-06", "480.00")
    assert c.vincular(rid, "2026-05", t["transacao_id"]).status_code == 200
    r = client.delete(
        f"/api/lancamentos/{t['transacao_id']}",
        params={"versao": t["versao"]},
        headers=escrita(c.csrf),
    )
    assert r.status_code == 204
    o = ocorrencias(client, "2026-05")[0]
    assert (o["vinculada"], o["valor"], o["transacao_id"]) == (False, "500.00", None)


def test_regras_do_vinculo(client: TestClient, usuario: Usuario) -> None:
    """SPEC-010-AC-13: tipo e conta da transação, uma transação por ocorrência e uma ocorrência por
    transação, mês fora do período, transação inexistente e desvincular sem vínculo."""
    c = Cenario(client, usuario)
    outra = c.conta("Outra", "corrente")
    a = c.recorrente("Fixo A", valor="500.00", inicio="2026-05", fim="2026-07")["recorrente_id"]
    b = c.recorrente("Fixo B", valor="90.00")["recorrente_id"]
    deb = c.debito("2026-05-06", "480.00")
    deb2 = c.debito("2026-05-07", "10.00")
    rec_tr = c.receita("2026-05-06", "480.00")
    em_outra = c.debito("2026-05-06", "480.00", conta=outra)

    def codigo(r: Any) -> tuple[int, str | None]:
        return r.status_code, r.headers.get("X-Abako-Erro")

    assert codigo(c.vincular(a, "2026-05", rec_tr["transacao_id"])) == (422, "AB422")
    assert codigo(c.vincular(a, "2026-05", em_outra["transacao_id"])) == (422, "AB422")
    assert codigo(c.vincular(a, "2026-08", deb["transacao_id"])) == (422, "AB422")
    assert codigo(c.vincular(a, "2026-04", deb["transacao_id"])) == (422, "AB422")
    assert codigo(c.vincular(a, "2026-13", deb["transacao_id"])) == (422, "AB422")
    assert codigo(c.vincular(a, "2026-05", 999_999_999)) == (404, "AB404")
    assert codigo(c.vincular(999_999_999, "2026-05", deb["transacao_id"])) == (404, "AB404")
    assert codigo(c.desvincular(a, "2026-05")) == (404, "AB404")

    assert c.vincular(a, "2026-05", deb["transacao_id"]).status_code == 200
    assert codigo(c.vincular(a, "2026-05", deb2["transacao_id"])) == (409, "AB410")
    assert codigo(c.vincular(b, "2026-05", deb["transacao_id"])) == (409, "AB410")
    assert ocorrencias(client, "2026-05")[0]["transacao_id"] == deb["transacao_id"]


def test_edicao_com_vinculo(client: TestClient, usuario: Usuario) -> None:
    """SPEC-010-AC-13: a edição vale para as ocorrências não vinculadas (a vinculada guarda o
    valor da transação); tipo/conta não mudam e o período não deixa vínculo de fora."""
    c = Cenario(client, usuario)
    outra = c.conta("Outra", "corrente")
    rec = c.recorrente("Fixo", valor="500.00", inicio="2026-05")
    rid = rec["recorrente_id"]
    t = c.debito("2026-05-06", "480.00")
    assert c.vincular(rid, "2026-05", t["transacao_id"]).status_code == 200
    url = f"/api/recorrentes/{rid}"

    r = client.put(
        url, json=c.corpo("Fixo", valor="600.00") | {"versao": 1}, headers=escrita(c.csrf)
    )
    assert r.status_code == 200 and r.json()["versao"] == 2
    maio, junho = ocorrencias(client, "2026-05")[0], ocorrencias(client, "2026-06")[0]
    assert (maio["valor_esperado"], maio["valor"]) == ("600.00", "480.00")
    assert (junho["valor_esperado"], junho["valor"]) == ("600.00", "600.00")

    for campos in (
        {"tipo": "receita"},
        {"conta": outra},
        {"inicio": "2026-06"},
        {"fim": "2026-04"},
    ):
        r = client.put(url, json=c.corpo("Fixo", **campos) | {"versao": 2}, headers=escrita(c.csrf))
        assert r.status_code == 422 and r.headers["X-Abako-Erro"] == "AB422", campos
    assert client.get(url).json()["versao"] == 2


# ------------------------------------------------------------------ sessão, CSRF, isolamento


ESCRITAS: list[tuple[str, str, dict[str, Any] | None]] = [
    ("post", "/api/recorrentes", {"nome": "x"}),
    ("put", "/api/recorrentes/1", {"nome": "x", "versao": 1}),
    ("delete", "/api/recorrentes/1?versao=1", None),
    ("put", "/api/recorrentes/1/ocorrencias/2026-05/vinculo", {"transacao_id": 1}),
    ("delete", "/api/recorrentes/1/ocorrencias/2026-05/vinculo", None),
]
LEITURAS = ["/api/recorrentes", "/api/recorrentes/1", "/api/recorrentes/ocorrencias"]


def test_sem_sessao_e_401(client: TestClient) -> None:
    """SPEC-010-AC-13: toda rota de recorrente exige sessão."""
    for url in LEITURAS:
        assert client.get(url).status_code == 401, url
    for metodo, url, corpo in ESCRITAS:
        r = getattr(client, metodo)(
            url, headers=ORIGEM, **({} if corpo is None else {"json": corpo})
        )
        assert r.status_code == 401, (metodo, url)


def test_escrita_sem_csrf_e_403_e_nada_e_gravado(client: TestClient, usuario: Usuario) -> None:
    """SPEC-010-AC-13: sem token CSRF (ou errado) toda escrita é 403 e nada muda."""
    c = Cenario(client, usuario)
    rec = c.recorrente("Aluguel")
    rid = rec["recorrente_id"]
    t = c.debito("2026-05-06", "10.00")
    errado = {**ORIGEM, "X-CSRF-Token": "errado"}
    corpo = c.corpo("Novo")
    chamadas = [
        ("post", "/api/recorrentes", corpo),
        ("put", f"/api/recorrentes/{rid}", corpo | {"versao": 1}),
        ("delete", f"/api/recorrentes/{rid}?versao=1", None),
        (
            "put",
            f"/api/recorrentes/{rid}/ocorrencias/2026-05/vinculo",
            {"transacao_id": t["transacao_id"]},
        ),
        ("delete", f"/api/recorrentes/{rid}/ocorrencias/2026-05/vinculo", None),
    ]
    for metodo, url, json in chamadas:
        for cab in (ORIGEM, errado):
            kw = {} if json is None else {"json": json}
            r = getattr(client, metodo)(url, headers=cab, **kw)
            assert r.status_code == 403, (metodo, url)
    lista = client.get("/api/recorrentes").json()
    assert [(x["nome"], x["versao"]) for x in lista] == [("Aluguel", 1)]
    assert ocorrencias(client, "2026-05")[0]["vinculada"] is False


def test_isolamento_entre_usuarios(
    client: TestClient, usuario: Usuario, outro_usuario: Usuario
) -> None:
    """SPEC-010-AC-11 e AC-13 (INV-13): o outro usuário não vê, edita, exclui nem vincula o
    recorrente do dono, e não usa conta nem transação dele; tudo volta 404."""
    c = Cenario(client, usuario)
    rid = c.recorrente("Aluguel", valor="500.00")["recorrente_id"]
    t = c.debito("2026-05-06", "480.00")
    assert c.vincular(rid, "2026-05", t["transacao_id"]).status_code == 200
    conta_dono = c.corrente
    client.post("/api/auth/logout", headers=escrita(c.csrf))
    client.cookies.clear()

    o = Cenario(client, outro_usuario)
    assert client.get("/api/recorrentes", params={"user_id": usuario.user_id}).json() == []
    assert ocorrencias(client, "2026-05") == []
    url = f"/api/recorrentes/{rid}"
    assert client.get(url).status_code == 404
    r = client.put(url, json=o.corpo("Aluguel") | {"versao": 2}, headers=escrita(o.csrf))
    assert r.status_code == 404 and r.headers["X-Abako-Erro"] == "AB404"
    r = client.delete(url, params={"versao": 2}, headers=escrita(o.csrf))
    assert r.status_code == 404
    assert o.vincular(rid, "2026-05", t["transacao_id"]).status_code == 404
    assert o.desvincular(rid, "2026-05").status_code == 404
    # Conta do dono num recorrente do outro usuário: 404; transação do dono: 404.
    r = client.post(
        "/api/recorrentes", json=o.corpo("Meu", conta=conta_dono), headers=escrita(o.csrf)
    )
    assert r.status_code == 404 and r.headers["X-Abako-Erro"] == "AB404"
    meu = o.recorrente("Meu")["recorrente_id"]
    assert o.vincular(meu, "2026-05", t["transacao_id"]).status_code == 404

    client.post("/api/auth/logout", headers=escrita(o.csrf))
    client.cookies.clear()
    logar(client, usuario)
    assert ocorrencias(client, "2026-05")[0]["transacao_id"] == t["transacao_id"]  # intacto


# ------------------------------------------------------------------ log e métodos


def test_nome_e_valores_fora_do_log(
    client: TestClient, usuario: Usuario, caplog: pytest.LogCaptureFixture
) -> None:
    """SPEC-010-AC-13: nem o nome do recorrente nem os valores vão a log, nas leituras e nas
    escritas (inclusive recusadas)."""
    c = Cenario(client, usuario)
    with caplog.at_level(logging.DEBUG):
        rec = c.recorrente("Nome-Sigiloso-QQ", valor="1234.56")
        t = c.debito("2026-05-06", "987.65")
        c.vincular(rec["recorrente_id"], "2026-05", t["transacao_id"])
        client.get("/api/recorrentes")
        ocorrencias(client, "2026-05")
        client.post(
            "/api/recorrentes",
            json=c.corpo("Nome-Sigiloso-QQ", valor="1234.56"),
            headers=escrita(c.csrf),
        )  # 409
        c.desvincular(rec["recorrente_id"], "2026-05")
    for texto in ("Nome-Sigiloso-QQ", "1234.56", "987.65"):
        assert texto not in caplog.text


def test_metodos_nao_previstos(client: TestClient, usuario: Usuario) -> None:
    """Coleção: GET e POST; ocorrências: só GET; vínculo: só PUT e DELETE."""
    csrf = logar(client, usuario)
    previstos = [
        ("put", "/api/recorrentes"),
        ("delete", "/api/recorrentes"),
        ("post", "/api/recorrentes/ocorrencias"),
        ("post", "/api/recorrentes/1"),
        ("post", "/api/recorrentes/1/ocorrencias/2026-05/vinculo"),
    ]
    for metodo, url in previstos:
        r = getattr(client, metodo)(url, headers=escrita(csrf))
        assert r.status_code == 405, (metodo, url)


@pytest.mark.parametrize("nome", ["a\x00b", "\x00", "a\x07b", "a\nb", "a\x7fb", "a\x85b"])
def test_nome_com_caractere_de_controle_e_422_sem_eco(
    client: TestClient, usuario: Usuario, nome: str
) -> None:
    """SPEC-010-AC-13: NUL e demais caracteres de controle no nome são 422 (nunca 500), na criação
    e na edição, sem eco do valor; nada é gravado."""
    c = Cenario(client, usuario)
    r = client.post("/api/recorrentes", json=c.corpo(nome), headers=escrita(c.csrf))
    assert r.status_code == 422, r.text
    assert all("input" not in erro for erro in r.json()["detail"])
    rec = c.recorrente("Aluguel")
    r = client.put(
        f"/api/recorrentes/{rec['recorrente_id']}",
        json=c.corpo(nome) | {"versao": 1},
        headers=escrita(c.csrf),
    )
    assert r.status_code == 422, r.text
    assert [x["nome"] for x in client.get("/api/recorrentes").json()] == ["Aluguel"]


def test_nome_com_espacos_nas_pontas_segue_valido(client: TestClient, usuario: Usuario) -> None:
    """SPEC-010-AC-13: espaços, tabulação e quebra de linha nas pontas são aparados."""
    c = Cenario(client, usuario)
    assert c.recorrente(" \tAluguel\n")["nome"] == "Aluguel"


@pytest.mark.parametrize("mes", ["2026-05\x00", "x" * 500, "2026-05\n", "2026-05 " * 3])
def test_mes_longo_ou_com_controle_e_ab422_literal(
    client: TestClient, usuario: Usuario, mes: str
) -> None:
    """SPEC-010-AC-13: mês com 500 caracteres ou com NUL/controle (query, caminho e corpo) é 422
    com X-Abako-Erro: AB422 e mensagem literal, nunca 500, sem eco."""
    c = Cenario(client, usuario)
    rid = c.recorrente("Aluguel")["recorrente_id"]
    t = c.debito("2026-05-06", "10.00")["transacao_id"]
    literal = "o mês precisa estar no formato AAAA-MM"

    r = client.get("/api/recorrentes/ocorrencias", params={"mes": mes})
    assert codigo(r) == (422, "AB422") and r.json()["detail"] == literal
    caminho = quote(mes, safe="")  # o cliente HTTP recusa controle cru na URL
    r = c.vincular(rid, caminho, t)
    assert codigo(r) == (422, "AB422") and r.json()["detail"] == literal
    r = c.desvincular(rid, caminho)
    assert codigo(r) == (422, "AB422") and r.json()["detail"] == literal
    r = client.post("/api/recorrentes", json=c.corpo("Outro", inicio=mes), headers=escrita(c.csrf))
    assert r.status_code == 422 and mes.strip() not in r.text
    assert [x["nome"] for x in client.get("/api/recorrentes").json()] == ["Aluguel"]


def codigo(r: Any) -> tuple[int, str | None]:
    return r.status_code, r.headers.get("X-Abako-Erro")
