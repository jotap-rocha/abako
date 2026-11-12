"""API de alertas R1, R2 e R4 (SPEC-011, ADR 049). Valores esperados vêm de F-ALERTA-01..04
(contas à mão); o que é alerta, a severidade e a ordem são do banco, a API só os repassa. Dinheiro é
texto; `hoje` é a data civil de São Paulo, injetada de forma determinística."""

from __future__ import annotations

import logging
from collections.abc import Callable, Iterator
from datetime import UTC, datetime
from typing import Any

import pytest
from fastapi.testclient import TestClient

from backend.services import gasto_real as svc_data
from tests.backend.conftest import Usuario, apagar_usuarios, criar_usuario, logar
from tests.backend.util_r2_api import Cenario, escrita, hoje_em
from tests.db.conftest import url_app  # noqa: F401  (fixture)
from tests.db.util_saldo import fixture

pytestmark = pytest.mark.banco

HOJE = "2026-05-10"


@pytest.fixture
def novo_usuario(esquema: str) -> Iterator[Callable[[], Usuario]]:
    """Fábrica de usuários (cada caso da fixture isola o seu), todos apagados no fim."""
    criados: list[Usuario] = []

    def criar() -> Usuario:
        u = criar_usuario(esquema, "a")
        criados.append(u)
        return u

    yield criar
    apagar_usuarios(esquema, criados)


@pytest.fixture
def outro_usuario(esquema: str) -> Iterator[Usuario]:
    u = criar_usuario(esquema, "o")
    yield u
    apagar_usuarios(esquema, [u])


def alertas_em(client: TestClient, hoje: str = HOJE) -> dict[str, Any]:
    with hoje_em(client, hoje):
        r = client.get("/api/alertas")
    assert r.status_code == 200, r.text
    corpo: dict[str, Any] = r.json()
    return corpo


def de(corpo: dict[str, Any], codigo: str) -> list[dict[str, Any]]:
    return [i for i in corpo["itens"] if i["codigo"] == codigo]


def chaves(itens: list[dict[str, Any]]) -> list[tuple[str, str, str, str]]:
    return [(i["codigo"], i["tipo"], i["severidade"], i["detalhe"]) for i in itens]


def sair(client: TestClient, c: Cenario) -> None:
    client.post("/api/auth/logout", headers=escrita(c.csrf))
    client.cookies.clear()


def esperado(e: dict[str, Any]) -> tuple[str, str, str, str]:
    return e["codigo"], e["tipo"], e["severidade"], e["detalhe"]


def r2_com(c: Cenario, fixo: str | None, cartao_sem_vencimento: bool = False) -> None:
    """F-ALERTA-02: receita recorrente de 3000.00 (dia 12) e um fixo (dia 15) sobre a corrente
    do Cenario (5000.00); opcionalmente um cartão com dívida de 300.00 e sem vencimento."""
    c.recorrente("Salario", tipo="receita", valor="3000.00", dia=12)
    if fixo is not None:
        c.recorrente("Aluguel", valor=fixo, dia=15)
    if cartao_sem_vencimento:
        cartao = c.cartao(10, None)
        c.compra(cartao, "2026-04-20", "300.00")


# ------------------------------------------------------------------ R1 (F-ALERTA-01)


def test_r1(client: TestClient, novo_usuario: Callable[[], Usuario]) -> None:
    """SPEC-011-AC-1: crítica = alerta alta; atenção = aviso media; saudável = nada."""
    f = fixture("F-ALERTA-01")
    for caso in f["casos"]:
        client.cookies.clear()
        c = Cenario(client, novo_usuario(), saldo=None)
        c.reserva("Caixinha", caso["saldo"])
        assert c.parametro_reserva(f["entrada"]["parametro"]["gasto_essencial"]).status_code == 200
        corpo = alertas_em(client, f["entrada"]["hoje"])
        r1 = de(corpo, "R1")
        if caso["alerta"] is None:
            assert r1 == [], caso["saldo"]
            continue
        assert chaves(r1) == [esperado(caso["alerta"])], caso["saldo"]
        assert r1[0]["reserva"] == {
            "nivel": caso["alerta"]["nivel"],
            "saldo_liquido": caso["saldo"],
            "meta": "12000.00",
            "falta": caso["alerta"]["falta"],
            "cobertura_meses": caso["alerta"]["cobertura_meses"],
        }
        assert r1[0]["r2"] is None and r1[0]["r4"] is None
        assert isinstance(r1[0]["mensagem"], str) and r1[0]["mensagem"]
        assert de(corpo, "CONFIG") == []


def test_config_pendente_nao_e_r1(client: TestClient, novo_usuario: Callable[[], Usuario]) -> None:
    """SPEC-011-AC-5: sem gasto essencial (ou zero) sai só o item de configuração."""
    f = fixture("F-ALERTA-01")["config_pendente"]
    esp = f["esperado"]
    for zero in (False, True):
        client.cookies.clear()
        c = Cenario(client, novo_usuario(), saldo=None)
        c.reserva("Caixinha", f["saldo"])
        if zero:
            assert c.parametro_reserva("0.00").status_code == 200
        corpo = alertas_em(client)
        assert chaves(corpo["itens"]) == [
            (esp["codigo"], esp["tipo"], esp["severidade"], esp["detalhe"])
        ]
        item = corpo["itens"][0]
        assert item["tipo"] == "configuracao"
        assert item["reserva"]["nivel"] is None and item["reserva"]["meta"] is None
        assert item["reserva"]["saldo_liquido"] == f["saldo"]
        assert de(corpo, "R1") == []


# ------------------------------------------------------------------ R2 (F-ALERTA-02)


def test_r2(client: TestClient, novo_usuario: Callable[[], Usuario]) -> None:
    """SPEC-011-AC-2: sobra negativa dispara o alerta forte, com os números em texto."""
    f = fixture("F-ALERTA-02")
    caso = next(c for c in f["casos"] if c["sobra"] == "-0.01")
    c = Cenario(client, novo_usuario(), saldo="5000.00")
    r2_com(c, caso["fixo"])
    r2 = de(alertas_em(client, f["entrada"]["hoje"]), "R2")
    assert chaves(r2) == [esperado(caso["alerta"])]
    assert r2[0]["r2"] == {
        "horizonte_dias": 10,
        "data_fim": "2026-05-20",
        "sobra": "-0.01",
        "disponivel": "8000.00",
        "compromissos": "8000.01",
        "sobra_nao_confiavel": False,
        "vencidas": 0,
        "pendencias_vencimento": 0,
    }
    assert r2[0]["reserva"] is None and r2[0]["r4"] is None


def test_r2_sobra_zero_ou_positiva_nao_alerta(
    client: TestClient, novo_usuario: Callable[[], Usuario]
) -> None:
    """SPEC-011-AC-4: sobra 0,01 e exatamente 0,00 não alertam (alerta só se < 0)."""
    f = fixture("F-ALERTA-02")
    for caso in (c for c in f["casos"] if c["alerta"] is None):
        client.cookies.clear()
        c = Cenario(client, novo_usuario(), saldo="5000.00")
        r2_com(c, caso["fixo"])
        assert de(alertas_em(client, f["entrada"]["hoje"]), "R2") == [], caso["fixo"]


def test_r2_sobra_nao_confiavel(client: TestClient, novo_usuario: Callable[[], Usuario]) -> None:
    """SPEC-011-AC-6: cartão com dívida sem vencimento marca a sobra, positiva ou negativa."""
    f = fixture("F-ALERTA-02")
    for caso in (c for c in f["casos"] if c.get("cartao_sem_vencimento")):
        client.cookies.clear()
        c = Cenario(client, novo_usuario(), saldo="5000.00")
        r2_com(c, caso["fixo"], cartao_sem_vencimento=True)
        r2 = de(alertas_em(client, f["entrada"]["hoje"]), "R2")
        assert chaves(r2) == [esperado(caso["alerta"])], caso["fixo"]
        assert r2[0]["r2"]["sobra"] == caso["sobra"]
        assert r2[0]["r2"]["sobra_nao_confiavel"] is True
        assert r2[0]["r2"]["pendencias_vencimento"] == caso["pendencias_vencimento"]


def test_r2_vencidas_sao_aviso_a_parte(client: TestClient, usuario: Usuario) -> None:
    """SPEC-011-AC-4: a vencida sem vínculo sai da sobra e vira aviso baixa com a quantidade."""
    f = fixture("F-ALERTA-02")["vencida"]
    c = Cenario(client, usuario, saldo="5000.00")
    c.recorrente("Salario", tipo="receita", valor="3000.00", dia=12)
    c.recorrente("Vencido", valor=f["fixo"]["valor"], dia=f["fixo"]["dia"])
    r2 = de(alertas_em(client), "R2")
    assert chaves(r2) == [esperado(f["esperado"]["alerta"])]
    assert r2[0]["r2"]["vencidas"] == f["esperado"]["vencidas"]
    assert r2[0]["r2"]["sobra"] == f["esperado"]["sobra"]
    assert r2[0]["r2"]["sobra_nao_confiavel"] is False


# ------------------------------------------------------------------ R4 (F-ALERTA-03)


def test_r4_visivel(client: TestClient, usuario: Usuario) -> None:
    """SPEC-011-AC-3: a divergência derivado x snapshot aparece na API, por conta (investimento e
    cartão), com a data, os valores e a quantidade; conta conferida e snapshot futuro não."""
    casos = {c["nome"]: c for c in fixture("F-ALERTA-03")["casos"]}
    c = Cenario(client, usuario, saldo=None)

    conta_a = c.conta("Conta A", "investimento", conta_mae_id=c.corrente)
    a = casos["conta_a"]
    c.snapshot(conta_a, a["snapshots"][0]["valor"], a["snapshots"][0]["data"])
    c.debito("2026-01-11", "50.00", conta=conta_a)
    c.receita("2026-01-12", "200.00", conta=conta_a)
    c.debito("2026-01-13", "100.00", conta=conta_a)
    c.snapshot(conta_a, a["snapshots"][1]["valor"], a["snapshots"][1]["data"])

    cartao = c.cartao(10, 20)
    k = casos["cartao"]
    c.snapshot(cartao, k["snapshots"][0]["valor"], k["snapshots"][0]["data"])
    c.compra(cartao, k["compra"]["data"], k["compra"]["total"])
    c.snapshot(cartao, k["snapshots"][1]["valor"], k["snapshots"][1]["data"])

    conferida = c.conta("Conferida", "investimento", conta_mae_id=c.corrente)
    c.snapshot(conferida, "500.00", "2026-01-10")
    c.debito("2026-01-12", "100.00", conta=conferida)
    c.snapshot(conferida, "400.00", "2026-01-14")

    corpo = alertas_em(client)
    r4 = de(corpo, "R4")
    assert {i["r4"]["conta_id"] for i in r4} == {conta_a, cartao}
    for item in r4:
        assert (item["tipo"], item["severidade"], item["detalhe"]) == (
            "aviso",
            "media",
            "divergencia_saldo",
        )
        assert item["reserva"] is None and item["r2"] is None
    por_conta = {i["r4"]["conta_id"]: i["r4"] for i in r4}
    assert por_conta[conta_a] == {
        "conta_id": conta_a,
        "data_snapshot": "2026-01-14",
        "valor_snapshot": "1040.00",
        "saldo_derivado": "1050.00",
        "divergencia": "10.00",
        "quantidade": 1,
    }
    assert por_conta[cartao] == {
        "conta_id": cartao,
        "data_snapshot": "2026-03-10",
        "valor_snapshot": "-550.00",
        "saldo_derivado": "-600.00",
        "divergencia": "-50.00",
        "quantidade": 1,
    }
    # a data de referência é a injetada: antes dos snapshots divergentes, não há R4
    assert de(alertas_em(client, "2026-01-05"), "R4") == []


# ------------------------------------------------------------------ combinação (F-ALERTA-04)


def test_varios_alertas_ordenados_por_severidade(client: TestClient, usuario: Usuario) -> None:
    """SPEC-011-AC-7: alta, media (R1 antes de R4), baixa; cada item com o seu bloco."""
    ordem = fixture("F-ALERTA-04")["esperado"]["ordem"]
    c = Cenario(client, usuario, saldo=None)
    c.reserva("Caixinha", "8000.00")
    assert c.parametro_reserva("4000.00").status_code == 200
    c.recorrente("Fixo futuro", valor="100.00", dia=15)
    c.recorrente("Fixo vencido", valor="50.00", dia=5)
    apl = c.conta("Aplicacao", "investimento", conta_mae_id=c.corrente)
    c.snapshot(apl, "1000.00", "2026-01-10")
    c.debito("2026-01-11", "50.00", conta=apl)
    c.snapshot(apl, "1000.00", "2026-01-14")

    corpo = alertas_em(client)
    assert corpo["data_referencia"] == HOJE
    assert chaves(corpo["itens"]) == [esperado(e) for e in ordem]
    sobra, r1, r4, vencidas = corpo["itens"]
    assert sobra["r2"]["sobra"] == "-100.00"
    assert (r1["reserva"]["nivel"], r1["reserva"]["falta"]) == ("atencao", "4000.00")
    assert (r4["r4"]["conta_id"], r4["r4"]["divergencia"]) == (apl, "-50.00")
    assert vencidas["r2"]["vencidas"] == 1


def test_usuario_novo_so_tem_a_configuracao_da_reserva(
    client: TestClient, usuario: Usuario
) -> None:
    logar(client, usuario)
    corpo = alertas_em(client)
    assert [(i["codigo"], i["tipo"], i["severidade"]) for i in corpo["itens"]] == [
        ("CONFIG", "configuracao", "baixa")
    ]


# ------------------------------------------------------------------ derivado na hora


def test_alerta_derivado_na_hora_sem_estado(client: TestClient, usuario: Usuario) -> None:
    """SPEC-011-AC-8: resolveu a condição, o alerta some; não há como dispensar nem gravar."""
    c = Cenario(client, usuario, saldo=None)
    caixinha = c.reserva("Caixinha", "3000.00")
    assert c.parametro_reserva("4000.00").status_code == 200
    antes = alertas_em(client, "2026-04-01")
    assert chaves(antes["itens"]) == [("R1", "alerta", "alta", "reserva_critica")]
    assert alertas_em(client, "2026-04-01") == antes  # repetir não muda nada
    # a reserva rende 9000.00: na consulta seguinte o alerta não existe mais
    r = client.post(
        "/api/lancamentos",
        json={
            "chave": "chave-alerta-0001",
            "tipo": "rendimento",
            "data": "2026-03-01",
            "bruto": "9000.00",
            "imposto": "0.00",
            "conta_id": caixinha,
        },
        headers=escrita(c.csrf),
    )
    assert r.status_code == 201, r.text
    assert alertas_em(client, "2026-04-01")["itens"] == []
    # só leitura: nenhum método de escrita ou dispensa existe
    for metodo in ("post", "put", "patch", "delete"):
        r = getattr(client, metodo)("/api/alertas", headers=escrita(c.csrf))
        assert r.status_code == 405, metodo


@pytest.mark.parametrize(
    ("utc", "esperado_hoje"),
    [
        (datetime(2027, 1, 1, 2, 30, tzinfo=UTC), "2026-12-31"),  # 23:30 em São Paulo
        (datetime(2027, 1, 1, 3, 30, tzinfo=UTC), "2027-01-01"),  # 00:30 em São Paulo
    ],
)
def test_hoje_usa_o_fuso_de_sao_paulo(
    client: TestClient,
    usuario: Usuario,
    monkeypatch: pytest.MonkeyPatch,
    utc: datetime,
    esperado_hoje: str,
) -> None:
    """SPEC-011-AC-10: o caminho de produção (sem override) decide pela data civil de SP."""
    logar(client, usuario)

    class RelogioFalso(datetime):
        @classmethod
        def now(cls, tz: Any = None) -> RelogioFalso:
            return cls.fromtimestamp(utc.timestamp(), tz)

    monkeypatch.setattr(svc_data, "datetime", RelogioFalso)
    r = client.get("/api/alertas")
    assert r.status_code == 200, r.text
    assert r.json()["data_referencia"] == esperado_hoje


def test_hoje_e_user_id_do_cliente_sao_ignorados(client: TestClient, usuario: Usuario) -> None:
    """SPEC-011-AC-10 e AC-9: nem `hoje` nem `user_id` na query mudam a consulta."""
    logar(client, usuario)
    base = alertas_em(client)
    with hoje_em(client, HOJE):
        r = client.get("/api/alertas", params={"hoje": "2000-01-01", "user_id": 999999})
    assert r.status_code == 200 and r.json() == base


# ------------------------------------------------------------------ segurança


def test_sem_sessao_e_401(client: TestClient) -> None:
    """SPEC-011-AC-10: a rota exige sessão."""
    assert client.get("/api/alertas").status_code == 401


def test_isolamento_entre_usuarios(
    client: TestClient, usuario: Usuario, outro_usuario: Usuario
) -> None:
    """SPEC-011-AC-9 (INV-13): o outro usuário não vê os alertas do dono."""
    c = Cenario(client, usuario, saldo="5000.00")
    c.reserva("Caixinha", "3000.00")
    assert c.parametro_reserva("4000.00").status_code == 200
    c.recorrente("Salario", tipo="receita", valor="3000.00", dia=12)
    c.recorrente("Aluguel", valor="9000.00", dia=15)
    apl = c.conta("Aplicacao", "investimento", conta_mae_id=c.corrente)
    c.snapshot(apl, "1000.00", "2026-01-10")
    c.snapshot(apl, "900.00", "2026-01-14")
    c.debito("2026-01-11", "50.00", conta=apl)
    dono = alertas_em(client)
    assert {i["codigo"] for i in dono["itens"]} == {"R1", "R2", "R4"}
    sair(client, c)

    Cenario(client, outro_usuario, saldo=None)
    corpo = alertas_em(client)
    assert [(i["codigo"], i["tipo"]) for i in corpo["itens"]] == [("CONFIG", "configuracao")]
    assert corpo["itens"][0]["reserva"]["saldo_liquido"] == "0.00"


def test_valores_e_nomes_fora_do_log(
    client: TestClient, usuario: Usuario, caplog: pytest.LogCaptureFixture
) -> None:
    """SPEC-011-AC-10: nenhum valor financeiro nem nome de conta ou de recorrente vai a log."""
    with caplog.at_level(logging.DEBUG):
        c = Cenario(client, usuario, saldo="5123.45")
        c.reserva("Reserva-Sigilosa-ZZ", "3456.78")
        c.parametro_reserva("4321.09")
        c.recorrente("Nome-Sigiloso-RR", valor="9876.54", dia=15)
        corpo = alertas_em(client)
        client.get("/api/alertas")
    assert {i["codigo"] for i in corpo["itens"]} == {"R1", "R2"}
    sobra = de(corpo, "R2")[0]["r2"]["sobra"]
    assert sobra == "-4753.09"  # 5123.45 - 9876.54
    for texto in (
        "Reserva-Sigilosa-ZZ",
        "Nome-Sigiloso-RR",
        "5123.45",
        "3456.78",
        "4321.09",
        "9876.54",
        "4753.09",
    ):
        assert texto not in caplog.text
    # as mensagens são literais: nenhum valor ou nome dentro delas
    for item in corpo["itens"]:
        assert not any(ch.isdigit() for ch in item["mensagem"].replace("50%", "")), item
        assert "Sigil" not in item["mensagem"]


def test_dinheiro_sempre_em_texto(client: TestClient, usuario: Usuario) -> None:
    """SPEC-011-AC-10 (INV-14): nenhum campo monetário sai como número."""
    c = Cenario(client, usuario, saldo="100.00")
    c.reserva("Caixinha", "3000.00")
    c.parametro_reserva("4000.00")
    c.recorrente("Aluguel", valor="900.00", dia=15)
    corpo = alertas_em(client)
    monetarios = ("saldo_liquido", "meta", "falta", "cobertura_meses", "sobra", "disponivel")
    achados = 0
    for item in corpo["itens"]:
        for bloco in ("reserva", "r2", "r4"):
            for campo, valor in (item[bloco] or {}).items():
                if campo in (*monetarios, "compromissos", "valor_snapshot", "divergencia"):
                    achados += 1
                    assert valor is None or isinstance(valor, str), (campo, valor)
    assert achados == 7  # R1: 4 campos; R2: sobra, disponivel e compromissos
