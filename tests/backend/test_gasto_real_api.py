"""API do gasto real e da receita do mês (SPEC-008, ADR 046). Valores esperados vêm de
F-GASTO-02 e F-GASTO-03 (calculados à mão); dinheiro é texto; o mês é o único dado na URL; o mês
padrão vem de America/Sao_Paulo e é injetado de forma determinística."""

from __future__ import annotations

import itertools
import logging
from collections.abc import Iterator
from datetime import UTC, date, datetime
from typing import Any

import pytest
from fastapi.testclient import TestClient

from backend.routers import gasto_real as router_gasto
from backend.services import gasto_real as svc_gasto
from tests.backend.conftest import ORIGEM, Usuario, apagar_usuarios, criar_usuario, logar

pytestmark = pytest.mark.banco

_contador = itertools.count(1)


def escrita(csrf: str) -> dict[str, str]:
    return {**ORIGEM, "X-CSRF-Token": csrf}


@pytest.fixture
def outro_usuario(esquema: str) -> Iterator[Usuario]:
    u = criar_usuario(esquema, "o")
    yield u
    apagar_usuarios(esquema, [u])


class Cenario:
    """Contas e lançamentos de um usuário, criados só pela API."""

    def __init__(self, client: TestClient, csrf: str) -> None:
        self.client = client
        self.csrf = csrf
        self.corrente = self.conta("Corrente")

    def conta(self, nome: str, tipo: str = "corrente", **campos: Any) -> int:
        corpo = {"nome": nome, "tipo": tipo, "conta_beneficio": tipo == "beneficio", **campos}
        r = self.client.post("/api/contas", json=corpo, headers=escrita(self.csrf))
        assert r.status_code == 201, r.text
        conta_id: int = r.json()["conta_id"]
        return conta_id

    def cartao(self) -> int:
        r = self.client.post(
            "/api/linhas-credito",
            json={"nome": "Linha", "limite": "5000"},
            headers=escrita(self.csrf),
        )
        assert r.status_code == 201, r.text
        cartao = self.conta("Cartão", "divida", linha_credito_id=r.json()["linha_id"])
        r = self.client.post(
            f"/api/cartoes/{cartao}/fechamentos",
            json={"dia": 10, "vigente_desde": "2025-01-01"},
            headers=escrita(self.csrf),
        )
        assert r.status_code == 201, r.text
        return cartao

    def pessoa(self, nome: str) -> int:
        r = self.client.post("/api/pessoas", json={"nome": nome}, headers=escrita(self.csrf))
        assert r.status_code == 201, r.text
        pessoa_id: int = r.json()["pessoa_id"]
        return pessoa_id

    def lancar(self, **campos: Any) -> dict[str, Any]:
        corpo = {"chave": f"chave-{next(_contador):08d}", **campos}
        r = self.client.post("/api/lancamentos", json=corpo, headers=escrita(self.csrf))
        assert r.status_code == 201, r.text
        saida: dict[str, Any] = r.json()
        return saida

    def compra(self, cartao: int, data: str, total: str, parcelas: int, **campos: Any) -> Any:
        return self.lancar(
            tipo="credito", data=data, valor=total, parcelas=parcelas, conta_id=cartao, **campos
        )

    def estornar(self, compra: dict[str, Any], data: str) -> None:
        r = self.client.post(
            f"/api/lancamentos/{compra['transacao_id']}/estorno",
            json={"versao": compra["versao"], "data": data},
            headers=escrita(self.csrf),
        )
        assert r.status_code == 201, r.text


def gasto(client: TestClient, mes: str) -> dict[str, Any]:
    r = client.get("/api/gasto-real", params={"mes": mes})
    assert r.status_code == 200, r.text
    corpo: dict[str, Any] = r.json()
    return corpo


def receita(client: TestClient, mes: str) -> dict[str, Any]:
    r = client.get("/api/receita", params={"mes": mes})
    assert r.status_code == 200, r.text
    corpo: dict[str, Any] = r.json()
    return corpo


def total_gasto(client: TestClient, mes: str) -> str:
    total: str = gasto(client, mes)["total"]
    return total


def mes_misto(client: TestClient, usuario: Usuario) -> tuple[Cenario, dict[str, int]]:
    """F-GASTO-02: parcelas de compras diferentes, reserva, rendimento, repasse, transferência,
    investimento, pagamento de fatura, terceiro e benefício. Fechamento no dia 10."""
    c = Cenario(client, logar(client, usuario))
    reserva = c.conta("Reserva", "reserva", conta_mae_id=c.corrente)
    invest = c.conta("Investimento", "investimento")
    vale = c.conta("Vale", "beneficio")
    cartao = c.cartao()
    b = c.pessoa("Pessoa B")

    c.compra(cartao, "2025-03-05", "300.00", 3)  # A: 100 em 03, 04, 05
    c.compra(cartao, "2025-03-12", "200.00", 2)  # B: 100 em 04, 05
    c.compra(cartao, "2025-04-05", "90.00", 1, pessoa_id=b)  # C: terceiro, fora do gasto

    c.lancar(tipo="debito", data="2025-03-31", valor="15.00", conta_id=c.corrente)
    c.lancar(tipo="debito", data="2025-04-08", valor="60.00", conta_id=c.corrente)
    c.lancar(tipo="debito", data="2025-04-09", valor="25.00", conta_id=reserva)
    c.lancar(tipo="debito", data="2025-04-10", valor="40.00", conta_id=vale)
    c.lancar(tipo="debito", data="2025-05-01", valor="11.00", conta_id=c.corrente)
    c.lancar(tipo="rendimento", data="2025-04-15", bruto="10.00", imposto="2.00", conta_id=reserva)
    c.lancar(
        tipo="transferencia",
        data="2025-04-16",
        valor="70.00",
        conta_id=c.corrente,
        conta_destino_id=reserva,
    )
    c.lancar(
        tipo="investimento",
        data="2025-04-17",
        valor="80.00",
        conta_id=c.corrente,
        conta_destino_id=invest,
    )
    c.lancar(  # pagamento de fatura é transferência para o cartão
        tipo="transferencia",
        data="2025-04-18",
        valor="150.00",
        conta_id=c.corrente,
        conta_destino_id=cartao,
    )
    c.lancar(tipo="repasse", data="2025-04-19", valor="30.00", conta_id=c.corrente, pessoa_id=b)
    c.lancar(tipo="receita", data="2025-03-20", valor="500.00", conta_id=c.corrente)
    c.lancar(tipo="receita", data="2025-04-02", valor="1000.00", conta_id=c.corrente)
    c.lancar(tipo="receita", data="2025-04-20", valor="250.00", conta_id=c.corrente)
    c.lancar(tipo="receita", data="2025-04-05", valor="400.00", conta_id=vale)
    return c, {"corrente": c.corrente, "reserva": reserva, "cartao": cartao}


def test_gasto_real_do_mes_f_gasto_02(client: TestClient, usuario: Usuario) -> None:
    """SPEC-008-AC-10 (gasto real): abril = 100 + 100 + 60 + 25 (terceiro, benefício, pagamento,
    transferência, investimento, repasse e rendimento fora); março, maio, junho: F-GASTO-02."""
    mes_misto(client, usuario)
    assert total_gasto(client, "2025-04") == "285.00"
    assert total_gasto(client, "2025-03") == "115.00"
    assert total_gasto(client, "2025-05") == "211.00"
    assert total_gasto(client, "2025-06") == "0.00"
    # A soma do ano (115 + 285 + 211) fica abaixo do total das saídas.
    assert gasto(client, "2025-06") == {"mes": "2025-06", "total": "0.00", "por_conta": []}


def test_gasto_por_conta_f_gasto_02(client: TestClient, usuario: Usuario) -> None:
    """SPEC-008-AC-10 (por conta): abril = corrente 60, reserva 25, cartão 200, em texto."""
    c, ids = mes_misto(client, usuario)
    corpo = gasto(client, "2025-04")
    assert corpo["mes"] == "2025-04"
    assert {(g["conta_id"], g["valor"]) for g in corpo["por_conta"]} == {
        (ids["corrente"], "60.00"),
        (ids["reserva"], "25.00"),
        (ids["cartao"], "200.00"),
    }
    assert [g["conta_id"] for g in corpo["por_conta"]] == sorted(
        g["conta_id"] for g in corpo["por_conta"]
    )
    assert all(isinstance(g["valor"], str) for g in corpo["por_conta"])
    assert isinstance(corpo["total"], str)
    assert c.corrente == ids["corrente"]


def test_receita_de_caixa_e_de_beneficio_f_gasto_02(client: TestClient, usuario: Usuario) -> None:
    """SPEC-008-AC-10 (receita): abril = caixa 1250,00 + benefício 400,00 = total 1650,00."""
    mes_misto(client, usuario)
    assert receita(client, "2025-04") == {
        "mes": "2025-04",
        "caixa": "1250.00",
        "beneficio": "400.00",
        "total": "1650.00",
    }
    assert receita(client, "2025-03") == {
        "mes": "2025-03",
        "caixa": "500.00",
        "beneficio": "0.00",
        "total": "500.00",
    }
    assert receita(client, "2025-06")["total"] == "0.00"


def test_estorno_tira_a_compra_das_competencias_originais_f_gasto_03(
    client: TestClient, usuario: Usuario
) -> None:
    """SPEC-008-AC-10 (estorno): a compra X (4x de 100) sai de 03, 04, 05 e 06, inclusive dos
    meses já fechados; o crédito do estorno não é receita nem gasto negativo."""
    c = Cenario(client, logar(client, usuario))
    cartao = c.cartao()
    x = c.compra(cartao, "2025-03-05", "400.00", 4)
    c.compra(cartao, "2025-03-06", "60.00", 1)
    c.lancar(tipo="debito", data="2025-03-15", valor="20.00", conta_id=c.corrente)
    c.lancar(tipo="debito", data="2025-04-08", valor="30.00", conta_id=c.corrente)
    c.lancar(
        tipo="transferencia",
        data="2025-04-15",
        valor="150.00",
        conta_id=c.corrente,
        conta_destino_id=cartao,
    )
    c.lancar(tipo="receita", data="2025-04-02", valor="1000.00", conta_id=c.corrente)

    antes = {m: total_gasto(client, m) for m in ("2025-03", "2025-04", "2025-05", "2025-06")}
    assert antes == {
        "2025-03": "180.00",
        "2025-04": "130.00",
        "2025-05": "100.00",
        "2025-06": "100.00",
    }

    c.estornar(x, "2025-04-20")
    depois = {m: total_gasto(client, m) for m in ("2025-03", "2025-04", "2025-05", "2025-06")}
    assert depois == {
        "2025-03": "80.00",
        "2025-04": "30.00",
        "2025-05": "0.00",
        "2025-06": "0.00",
    }
    assert receita(client, "2025-04")["caixa"] == "1000.00"


def test_mes_padrao_e_o_corrente_injetado(client: TestClient, usuario: Usuario) -> None:
    """SPEC-008-AC-10 (mês padrão): sem `mes`, vale o mês de hoje; `mes` explícito prevalece."""
    mes_misto(client, usuario)
    app: Any = client.app
    app.dependency_overrides[router_gasto.hoje_civil] = lambda: date(2025, 4, 20)
    try:
        padrao = client.get("/api/gasto-real")
        assert padrao.status_code == 200 and padrao.json()["mes"] == "2025-04"
        assert padrao.json()["total"] == "285.00"
        assert client.get("/api/receita").json()["total"] == "1650.00"
        assert client.get("/api/gasto-real", params={"mes": "2025-03"}).json()["total"] == "115.00"
    finally:
        app.dependency_overrides.clear()


def _relogio_em(monkeypatch: pytest.MonkeyPatch, instante_utc: datetime) -> None:
    class RelogioFalso(datetime):
        @classmethod
        def now(cls, tz: Any = None) -> RelogioFalso:
            return cls.fromtimestamp(instante_utc.timestamp(), tz)

    monkeypatch.setattr(svc_gasto, "datetime", RelogioFalso)


@pytest.mark.parametrize(
    ("utc", "mes"),
    [
        (datetime(2025, 5, 1, 2, 30, tzinfo=UTC), "2025-04"),  # 30/04 23:30 em São Paulo
        (datetime(2025, 5, 1, 3, 30, tzinfo=UTC), "2025-05"),  # 01/05 00:30 em São Paulo
        (datetime(2026, 1, 1, 2, 30, tzinfo=UTC), "2025-12"),  # 31/12 23:30 em São Paulo
        (datetime(2026, 1, 1, 3, 30, tzinfo=UTC), "2026-01"),  # 01/01 00:30 em São Paulo
    ],
)
def test_mes_padrao_usa_o_fuso_de_sao_paulo_na_virada(
    client: TestClient, usuario: Usuario, monkeypatch: pytest.MonkeyPatch, utc: datetime, mes: str
) -> None:
    """SPEC-008-AC-10: o caminho de produção (hoje_civil, sem override) decide o mês pelo fuso
    de São Paulo, não por UTC, nas viradas de mês e de ano."""
    logar(client, usuario)
    _relogio_em(monkeypatch, utc)
    assert router_gasto.hoje_civil().strftime("%Y-%m") == mes
    assert client.get("/api/gasto-real").json()["mes"] == mes
    assert client.get("/api/receita").json()["mes"] == mes


def test_conta_de_beneficio_vale_pelo_tipo_vigente_na_consulta(
    client: TestClient, usuario: Usuario
) -> None:
    """SPEC-008-AC-10 (ADR 046 item 6): o benefício vale pelo tipo vigente da conta; o banco
    recusa trocar o tipo de conta com lançamentos, então meses passados não são reescritos."""
    c = Cenario(client, logar(client, usuario))
    conta = c.conta("Vale", "beneficio")
    c.lancar(tipo="debito", data="2025-03-10", valor="40.00", conta_id=conta)
    c.lancar(tipo="receita", data="2025-03-05", valor="400.00", conta_id=conta)
    assert total_gasto(client, "2025-03") == "0.00"
    corpo = receita(client, "2025-03")
    assert (corpo["caixa"], corpo["beneficio"], corpo["total"]) == ("0.00", "400.00", "400.00")

    r = client.put(
        f"/api/contas/{conta}",
        json={"nome": "Vale", "tipo": "corrente", "versao": 1},
        headers=escrita(c.csrf),
    )
    assert r.status_code == 422 and r.headers["X-Abako-Erro"] == "AB422"
    assert total_gasto(client, "2025-03") == "0.00"
    assert receita(client, "2025-03")["beneficio"] == "400.00"

    # Sem lançamentos a troca é aceita, e o tipo novo vale dali em diante.
    vazia = c.conta("Outra", "beneficio")
    r = client.put(
        f"/api/contas/{vazia}",
        json={"nome": "Outra", "tipo": "corrente", "versao": 1},
        headers=escrita(c.csrf),
    )
    assert r.status_code == 200, r.text
    c.lancar(tipo="debito", data="2025-03-11", valor="7.00", conta_id=vazia)
    assert total_gasto(client, "2025-03") == "7.00"


@pytest.mark.parametrize(
    "mes", ["2025-13", "2025-00", "2025-4", "25-04", "abril", "2025/04", " ", "x" * 500]
)
def test_mes_invalido_e_422_do_banco(client: TestClient, usuario: Usuario, mes: str) -> None:
    """SPEC-008-AC-10: mês fora de AAAA-MM é recusado (422/AB422), com mensagem literal."""
    logar(client, usuario)
    for rota in ("/api/gasto-real", "/api/receita"):
        r = client.get(rota, params={"mes": mes})
        assert r.status_code == 422, (rota, r.text)
        assert r.headers["X-Abako-Erro"] == "AB422"
        assert r.json()["detail"] == "o mês precisa estar no formato AAAA-MM"
    # Nada ficou preso na conexão: a próxima chamada válida funciona.
    assert total_gasto(client, "2025-04") == "0.00"


def test_isolamento_entre_usuarios(
    client: TestClient, usuario: Usuario, outro_usuario: Usuario
) -> None:
    """SPEC-008-AC-10 (INV-13): o outro usuário não vê nada; `user_id` na query é ignorado."""
    mes_misto(client, usuario)
    client.post("/api/auth/logout", headers=escrita(logar(client, usuario)))
    client.cookies.clear()
    logar(client, outro_usuario)
    r = client.get("/api/gasto-real", params={"mes": "2025-04", "user_id": 1})
    assert r.json() == {"mes": "2025-04", "total": "0.00", "por_conta": []}
    r = client.get("/api/receita", params={"mes": "2025-04", "user_id": 1})
    assert r.json() == {"mes": "2025-04", "caixa": "0.00", "beneficio": "0.00", "total": "0.00"}


def test_sem_sessao_e_401(client: TestClient) -> None:
    """SPEC-008-AC-10: as duas rotas exigem sessão."""
    for rota in ("/api/gasto-real", "/api/receita"):
        assert client.get(rota, params={"mes": "2025-04"}).status_code == 401
        assert client.get(rota).status_code == 401


def test_valores_fora_do_log(
    client: TestClient, usuario: Usuario, caplog: pytest.LogCaptureFixture
) -> None:
    """SPEC-008-AC-10: nenhum valor financeiro vai a log nas leituras."""
    mes_misto(client, usuario)
    with caplog.at_level(logging.DEBUG):
        gasto(client, "2025-04")
        receita(client, "2025-04")
    for valor in ("285.00", "1250.00", "1650.00", "400.00"):
        assert valor not in caplog.text


def test_leituras_nao_gravam_e_so_get(client: TestClient, usuario: Usuario) -> None:
    """GET só leitura: POST/PUT/DELETE nas rotas novas não existem (405)."""
    csrf = logar(client, usuario)
    for rota in ("/api/gasto-real", "/api/receita"):
        for metodo in ("post", "put", "delete"):
            r = getattr(client, metodo)(rota, headers=escrita(csrf))
            assert r.status_code == 405, (rota, metodo)
