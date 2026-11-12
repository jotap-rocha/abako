"""API da situação do R2, do horizonte e do vencimento do cartão (SPEC-010, ADR 048). Valores
esperados vêm de F-R2-01..09 (contas à mão); a sobra, o alerta e a fatura própria são do banco, a
API só os repassa. Dinheiro é texto; `hoje` é a data civil de São Paulo, injetada."""

from __future__ import annotations

import logging
from collections.abc import Iterator
from datetime import UTC, datetime
from typing import Any

import psycopg
import pytest
from fastapi.testclient import TestClient

from backend.services import gasto_real as svc_data
from backend.services import r2 as r2_servico
from tests.backend.conftest import (
    ORIGEM,
    Usuario,
    apagar_usuarios,
    criar_usuario,
    logar,
)
from tests.backend.util_r2_api import Cenario, escrita, hoje_em, r2_em, resumo
from tests.db.conftest import url_app  # noqa: F401  (fixture)

pytestmark = pytest.mark.banco

TOTAIS = (
    "saldos_correntes",
    "receitas_pendentes",
    "disponivel",
    "fixos_pendentes",
    "faturas_proprias",
    "compromissos",
    "sobra",
    "alerta",
)


@pytest.fixture
def outro_usuario(esquema: str) -> Iterator[Usuario]:
    u = criar_usuario(esquema, "o")
    yield u
    apagar_usuarios(esquema, [u])


def codigo(r: Any) -> tuple[int, str | None]:
    return r.status_code, r.headers.get("X-Abako-Erro")


# ------------------------------------------------------------------ sobra (F-R2-01..03)


@pytest.mark.parametrize(
    ("fatura", "compromissos", "sobra", "alerta"),
    [
        ("4200.00", "6700.00", "1300.00", False),  # F-R2-01
        ("6000.00", "8500.00", "-500.00", True),  # F-R2-02
    ],
)
def test_sobra_positiva_e_negativa_f_r2_01_e_02(
    client: TestClient, usuario: Usuario, fatura: str, compromissos: str, sobra: str, alerta: bool
) -> None:
    """SPEC-010-AC-1 e AC-13 (F-R2-01, F-R2-02): hoje 10/05, horizonte 10; saldo 5000,00, receita
    3000,00, fixo 2500,00 e fatura própria no horizonte. Disponível 8000,00; a sobra e o alerta
    vêm do banco."""
    c = Cenario(client, usuario, saldo="5000.00")
    c.recorrente("Salario", tipo="receita", valor="3000.00", dia=15, fim="2026-05")
    fixo = c.recorrente("Aluguel", valor="2500.00", dia=12, fim="2026-05")
    cartao = c.cartao(fechamento=10, vencimento=20)
    c.compra(cartao, "2026-04-20", fatura)  # competência 2026-05, vence 20/05 = hoje + 10

    s = r2_em(client, "2026-05-10")
    assert resumo(s, *TOTAIS) == {
        "saldos_correntes": "5000.00",
        "receitas_pendentes": "3000.00",
        "disponivel": "8000.00",
        "fixos_pendentes": "2500.00",
        "faturas_proprias": fatura,
        "compromissos": compromissos,
        "sobra": sobra,
        "alerta": alerta,
    }
    assert (s["horizonte_dias"], s["data_fim"]) == (10, "2026-05-20")
    assert (s["vencidas"], s["pendencias_vencimento"]) == (0, 0)
    assert [(i["grupo"], i["data"], i["valor"]) for i in s["itens"]] == [
        ("fatura", "2026-05-20", fatura),
        ("fixo", "2026-05-12", "2500.00"),
        ("receita", "2026-05-15", "3000.00"),
    ]
    item_fatura = s["itens"][0]
    assert item_fatura == {
        "grupo": "fatura",
        "tipo": None,
        "recorrente_id": None,
        "conta_id": cartao,
        "competencia": "2026-05",
        "data": "2026-05-20",
        "valor": fatura,
        "bruto": fatura,
        "pago": "0.00",
        "parcial": False,
    }
    assert s["itens"][1]["recorrente_id"] == fixo["recorrente_id"]
    assert all(isinstance(s[k], str) for k in TOTAIS if k != "alerta")


def test_terceiros_vale_e_outras_contas_fora_da_sobra_f_r2_03(
    client: TestClient, usuario: Usuario
) -> None:
    """SPEC-010-AC-1, AC-2, AC-8 e AC-13 (F-R2-03, INV-18, INV-26): a fatura de 5000,00 tem 800,00
    de terceiro; só os 4200,00 próprios entram. O crédito do vale (1000,00 no benefício), a reserva
    e o investimento não entram no disponível. Sobra 1300,00."""
    c = Cenario(client, usuario, saldo="5000.00")
    c.recorrente("Salario", tipo="receita", valor="3000.00", dia=15, fim="2026-05")
    c.recorrente("Aluguel", valor="2500.00", dia=12, fim="2026-05")
    vale = c.conta("Vale", "beneficio")
    c.snapshot(vale, "0.00")
    c.receita("2026-05-02", "1000.00", conta=vale)
    reserva = c.conta("Reserva", "reserva", conta_mae_id=c.corrente)
    c.snapshot(reserva, "9999.00")
    invest = c.conta("Invest", "investimento")
    c.snapshot(invest, "7777.00")
    cartao = c.cartao(fechamento=10, vencimento=20)
    pessoa = c.pessoa()
    c.compra(cartao, "2026-04-20", "4200.00")
    c.compra(cartao, "2026-04-15", "800.00", pessoa_id=pessoa)

    fatura = client.get(f"/api/cartoes/{cartao}/faturas/2026-05").json()
    assert (fatura["total"], fatura["propria"], fatura["terceiros"]) == (
        "5000.00",
        "4200.00",
        "800.00",
    )
    s = r2_em(client, "2026-05-10")
    assert resumo(s, "saldos_correntes", "faturas_proprias", "compromissos", "sobra") == {
        "saldos_correntes": "5000.00",
        "faturas_proprias": "4200.00",
        "compromissos": "6700.00",
        "sobra": "1300.00",
    }
    assert s["alerta"] is False
    item = next(i for i in s["itens"] if i["grupo"] == "fatura")
    assert (item["valor"], item["bruto"]) == ("4200.00", "4200.00")


# ------------------------------------------------------------------ vinculada, vencida, limites


def test_vinculada_sai_e_vencida_fica_a_parte_f_r2_04(client: TestClient, usuario: Usuario) -> None:
    """SPEC-010-AC-1 e AC-13 (F-R2-04, INV-19): hoje 10/05, saldo 0,00. fixo_a (05/05, 400,00)
    vencido e não vinculado: lista `vencida`, fora da sobra. fixo_b (12/05, 300,00) vinculado a um
    débito de 08/05: fora. fixo_c (15/05, 200,00) entra. fixo_d (25/05) está além do horizonte.
    Compromissos 200,00; o débito de 300,00 já saiu do saldo (-300,00), logo a sobra é -500,00."""
    c = Cenario(client, usuario, saldo="0.00")
    a = c.recorrente("fixo_a", valor="400.00", dia=5, fim="2026-05")
    b = c.recorrente("fixo_b", valor="300.00", dia=12, fim="2026-05")
    cc = c.recorrente("fixo_c", valor="200.00", dia=15, fim="2026-05")
    c.recorrente("fixo_d", valor="999.00", dia=25, fim="2026-05")
    t = c.debito("2026-05-08", "300.00")
    assert c.vincular(b["recorrente_id"], "2026-05", t["transacao_id"]).status_code == 200

    s = r2_em(client, "2026-05-10")
    assert resumo(
        s, "saldos_correntes", "fixos_pendentes", "compromissos", "sobra", "alerta", "vencidas"
    ) == {
        "saldos_correntes": "-300.00",
        "fixos_pendentes": "200.00",
        "compromissos": "200.00",
        "sobra": "-500.00",
        "alerta": True,
        "vencidas": 1,
    }
    assert [(i["grupo"], i["recorrente_id"], i["data"], i["valor"]) for i in s["itens"]] == [
        ("fixo", cc["recorrente_id"], "2026-05-15", "200.00"),
        ("vencida", a["recorrente_id"], "2026-05-05", "400.00"),
    ]

    # Desvincular devolve fixo_b ao R2: fixos 200,00 + 300,00; sobra -300,00 - 500,00.
    assert c.desvincular(b["recorrente_id"], "2026-05").status_code == 200
    s = r2_em(client, "2026-05-10")
    assert (s["fixos_pendentes"], s["sobra"]) == ("500.00", "-800.00")
    # Vincular a vencida a um débito de 05/05 (400,00) a tira da lista.
    pago = c.debito("2026-05-05", "400.00")
    assert c.vincular(a["recorrente_id"], "2026-05", pago["transacao_id"]).status_code == 200
    s = r2_em(client, "2026-05-10")
    assert s["vencidas"] == 0 and all(i["grupo"] != "vencida" for i in s["itens"])


def test_vinculo_de_fixo_f_r2_11(client: TestClient, usuario: Usuario) -> None:
    """SPEC-010-AC-4 e AC-13 (F-R2-11): hoje 10/05, fixo de 500,00 no dia 12, débito de 480,00 em
    08/05. Antes: ocorrência de 12/05 por 500,00, compromissos 500,00. Vinculada: 480,00 e
    compromissos 0,00. Desvinculada: 500,00 e compromissos 500,00."""
    c = Cenario(client, usuario, saldo="0.00")
    rid = c.recorrente("Fixo", valor="500.00", dia=12, fim="2026-05")["recorrente_id"]
    t = c.debito("2026-05-08", "480.00")
    url = "/api/recorrentes/ocorrencias"
    antes = client.get(url, params={"mes": "2026-05"}).json()[0]
    assert (antes["data"], antes["valor"], antes["vinculada"]) == ("2026-05-12", "500.00", False)
    assert r2_em(client, "2026-05-10")["compromissos"] == "500.00"
    assert c.vincular(rid, "2026-05", t["transacao_id"]).status_code == 200
    s = r2_em(client, "2026-05-10")
    assert (s["compromissos"], s["fixos_pendentes"]) == ("0.00", "0.00")
    depois = client.get(url, params={"mes": "2026-05"}).json()[0]
    assert (depois["valor"], depois["vinculada"]) == ("480.00", True)
    assert c.desvincular(rid, "2026-05").status_code == 200
    assert r2_em(client, "2026-05-10")["compromissos"] == "500.00"
    depois = client.get(url, params={"mes": "2026-05"}).json()[0]
    assert (depois["valor"], depois["vinculada"]) == ("500.00", False)


@pytest.mark.parametrize(
    ("pagamento", "pago_proprio", "faturas", "saldo", "sobra"),
    [
        ("500.00", "0.00", "600.00", "2500.00", "1900.00"),  # 100,00 + 400,00 de terceiro
        ("60.00", "0.00", "600.00", "2940.00", "2340.00"),  # nem cobre a competência mais antiga
        ("800.00", "300.00", "300.00", "2200.00", "1900.00"),  # 100,00 + 400,00 + 300,00
    ],
)
def test_pago_com_terceiro_anterior_f_r2_12(
    client: TestClient,
    usuario: Usuario,
    pagamento: str,
    pago_proprio: str,
    faturas: str,
    saldo: str,
    sobra: str,
) -> None:
    """SPEC-010-AC-7 e AC-13 (F-R2-12): fechamento 10, vencimento 20, hoje 10/05, saldo 3000,00.
    Compras: 100,00 própria (competência abril), 400,00 de pessoa e 600,00 própria (maio, a de
    terceiro vem antes). O pago segue a ordem das parcelas sem distinguir dono."""
    c = Cenario(client, usuario, saldo="3000.00")
    cartao = c.cartao(10, 20)
    pessoa = c.pessoa()
    c.compra(cartao, "2026-03-12", "100.00")
    c.compra(cartao, "2026-04-11", "400.00", pessoa_id=pessoa)
    c.compra(cartao, "2026-04-15", "600.00")
    c.pagar(cartao, "2026-04-30", pagamento)
    s = r2_em(client, "2026-05-10")
    assert resumo(s, "saldos_correntes", "faturas_proprias", "sobra") == {
        "saldos_correntes": saldo,
        "faturas_proprias": faturas,
        "sobra": sobra,
    }
    assert [(i["bruto"], i["pago"]) for i in s["itens"]] == [("600.00", pago_proprio)]


def test_vigencia_retroativa_do_vencimento_f_r2_13(client: TestClient, usuario: Usuario) -> None:
    """SPEC-010-AC-6 e AC-13 (F-R2-13): hoje 02/05, saldo 2000,00, fechamento 25 desde 01/01 e
    vencimento 5 cadastrado só com vigente_desde = hoje. A competência 2026-04 (900,00) vence em
    05/05, dentro do horizonte, e pesa: sobra 1100,00; nenhuma pendência de vencimento."""
    c = Cenario(client, usuario, saldo="2000.00")
    cartao = c.cartao(25, None)
    assert c.vencimento(cartao, 5, "2026-05-02").status_code == 200
    c.compra(cartao, "2026-03-30", "900.00")
    s = r2_em(client, "2026-05-02")
    assert resumo(s, "faturas_proprias", "sobra", "pendencias_vencimento") == {
        "faturas_proprias": "900.00",
        "sobra": "1100.00",
        "pendencias_vencimento": 0,
    }
    assert [(i["competencia"], i["data"]) for i in s["itens"]] == [("2026-04", "2026-05-05")]


def test_data_futura_nao_abate_f_r2_14(client: TestClient, usuario: Usuario) -> None:
    """SPEC-010-AC-7 e AC-13 (F-R2-14): o pagamento de 450,00 (cenário F-R2-07) com data 15/05
    não abate em 10/05 (saldo 3000,00, fatura 1000,00, sobra 2000,00) e abate em 15/05 (saldo
    2550,00, fatura 750,00, sobra 1800,00)."""
    c = Cenario(client, usuario, saldo="3000.00")
    cartao = c.cartao(10, 20)
    pessoa = c.pessoa()
    c.compra(cartao, "2026-03-20", "200.00")
    c.compra(cartao, "2026-04-12", "1000.00")
    c.compra(cartao, "2026-04-15", "300.00", pessoa_id=pessoa)
    c.pagar(cartao, "2026-05-15", "450.00")
    campos = ("saldos_correntes", "faturas_proprias", "sobra")
    assert resumo(r2_em(client, "2026-05-10"), *campos) == {
        "saldos_correntes": "3000.00",
        "faturas_proprias": "1000.00",
        "sobra": "2000.00",
    }
    assert resumo(r2_em(client, "2026-05-15"), *campos) == {
        "saldos_correntes": "2550.00",
        "faturas_proprias": "750.00",
        "sobra": "1800.00",
    }


def test_vinculo_com_data_futura_continua_pendente_f_r2_14(
    client: TestClient, usuario: Usuario
) -> None:
    """SPEC-010-AC-4 e AC-13 (F-R2-14): saldo 1000,00, fixo de 500,00 no dia 12 vinculado a um
    débito de 480,00 em 12/05. Em 10/05 a ocorrência segue pendente (fixos 500,00, saldo 1000,00,
    sobra 500,00); em 12/05 sai (fixos 0,00, saldo 520,00, sobra 520,00)."""
    c = Cenario(client, usuario, saldo="1000.00")
    rid = c.recorrente("Fixo", valor="500.00", dia=12, fim="2026-05")["recorrente_id"]
    t = c.debito("2026-05-12", "480.00")
    assert c.vincular(rid, "2026-05", t["transacao_id"]).status_code == 200
    campos = ("fixos_pendentes", "saldos_correntes", "sobra")
    assert resumo(r2_em(client, "2026-05-10"), *campos) == {
        "fixos_pendentes": "500.00",
        "saldos_correntes": "1000.00",
        "sobra": "500.00",
    }
    assert resumo(r2_em(client, "2026-05-12"), *campos) == {
        "fixos_pendentes": "0.00",
        "saldos_correntes": "520.00",
        "sobra": "520.00",
    }


def test_vencidas_so_24_meses_f_r2_15(client: TestClient, usuario: Usuario) -> None:
    """SPEC-010-AC-3 e AC-13 (F-R2-15): hoje 10/05/2026; recorrentes desde 2020-01 nos dias 15, 5
    e 10, nenhum vinculado. Cada um lista 24 vencidas (piso 10/05/2024, inclusive)."""
    c = Cenario(client, usuario, saldo="0.00")
    ids = {
        dia: c.recorrente(f"dia_{dia}", dia=dia, inicio="2020-01")["recorrente_id"]
        for dia in (15, 5, 10)
    }
    s = r2_em(client, "2026-05-10")
    assert s["vencidas"] == 72
    esperado = {
        15: ("2024-05-15", "2026-04-15"),
        5: ("2024-06-05", "2026-05-05"),
        10: ("2024-05-10", "2026-04-10"),
    }
    for dia, (primeira, ultima) in esperado.items():
        datas = sorted(
            i["data"]
            for i in s["itens"]
            if i["grupo"] == "vencida" and i["recorrente_id"] == ids[dia]
        )
        assert (len(datas), datas[0], datas[-1]) == (24, primeira, ultima), dia


def test_situacao_e_itens_na_mesma_transacao(
    client: TestClient,
    usuario: Usuario,
    url_app: str,  # noqa: F811
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """SPEC-010-AC-13: `GET /r2` lê os totais e os itens numa transação REPEATABLE READ somente
    leitura. Um recorrente gravado e commitado por outra conexão entre as duas leituras não
    aparece nos itens, que seguem batendo com os totais."""
    c = Cenario(client, usuario, saldo="0.00")
    c.recorrente("Fixo A", valor="100.00", dia=12, fim="2026-05")
    original = r2_servico.itens
    vistos: list[tuple[str, str]] = []

    async def itens_com_escrita_concorrente(conn: Any, user_id: int, hoje: Any) -> Any:
        for var in ("transaction_isolation", "transaction_read_only"):
            cur = await conn.execute(f"SHOW {var}")
            linha = await cur.fetchone()
            vistos.append((var, linha[0]))
        with psycopg.connect(url_app) as outra:
            outra.execute(
                "SELECT recorrente_gravar(%s, NULL, NULL, 'Fixo B', 'fixo', 50.00, 12, %s, "
                "'2026-05', '2026-05')",
                (user_id, c.corrente),
            )
        return await original(conn, user_id, hoje)

    monkeypatch.setattr(r2_servico, "itens", itens_com_escrita_concorrente)
    s = r2_em(client, "2026-05-10")
    assert vistos == [("transaction_isolation", "repeatable read"), ("transaction_read_only", "on")]
    assert (s["fixos_pendentes"], len(s["itens"])) == ("100.00", 1)
    monkeypatch.setattr(r2_servico, "itens", original)
    assert r2_em(client, "2026-05-10")["fixos_pendentes"] == "150.00"  # a escrita existiu


def test_vigencia_a_mais_de_5_anos_no_futuro_e_ab422(client: TestClient, usuario: Usuario) -> None:
    """SPEC-010-AC-9 e AC-13: horizonte e vencimento com `vigente_desde` além de 5 anos no futuro
    voltam 422 com X-Abako-Erro: AB422 e mensagem literal; nada é gravado."""
    c = Cenario(client, usuario)
    cartao = c.cartao(10, None)
    r = c.horizonte(10, "2099-01-01")
    assert codigo(r) == (422, "AB422") and "2099" not in r.text
    r = c.vencimento(cartao, 10, "2099-01-01")
    assert codigo(r) == (422, "AB422") and "2099" not in r.text
    assert client.get("/api/r2/horizonte").json() == []
    assert client.get(f"/api/cartoes/{cartao}/vencimentos").json() == []


@pytest.mark.parametrize(
    ("hoje", "fixos", "receitas", "disponivel", "sobra", "vencidas"),
    [
        # fim = hoje + 10. Cada dia da fixture entra ou sai conforme o limite inclusivo.
        ("2026-05-10", "300.00", "50.00", "1050.00", "750.00", 1),  # F-R2-05
        # hoje 09, fim 19: fixos dos dias 9 e 10 (900,00); as receitas dos dias 20 e 21 ficam fora.
        ("2026-05-09", "900.00", "0.00", "1000.00", "100.00", 0),
        # hoje 11, fim 21: dias 9 e 10 vencidos; fixos 200,00 + 400,00; receitas 50,00 + 7000,00.
        ("2026-05-11", "600.00", "7050.00", "8050.00", "7450.00", 2),
    ],
)
def test_limites_do_horizonte_f_r2_05(
    client: TestClient,
    usuario: Usuario,
    hoje: str,
    fixos: str,
    receitas: str,
    disponivel: str,
    sobra: str,
    vencidas: int,
) -> None:
    """SPEC-010-AC-3 e AC-13 (F-R2-05): horizonte 10, saldo 1000,00. Fixos nos dias 9 (800,00),
    10 (100,00), 20 (200,00), 21 (400,00); receitas nos dias 20 (50,00) e 21 (7000,00). No dia 10:
    hoje e hoje + 10 entram, o dia 21 não e o dia 9 é vencida. Os outros `hoje` movem o limite."""
    c = Cenario(client, usuario, saldo="1000.00")
    for nome, dia, valor in (
        ("fixo_ontem", 9, "800.00"),
        ("fixo_hoje", 10, "100.00"),
        ("fixo_ultimo", 20, "200.00"),
        ("fixo_depois", 21, "400.00"),
    ):
        c.recorrente(nome, valor=valor, dia=dia, fim="2026-05")
    c.recorrente("receita_ultimo", tipo="receita", valor="50.00", dia=20, fim="2026-05")
    c.recorrente("receita_depois", tipo="receita", valor="7000.00", dia=21, fim="2026-05")

    s = r2_em(client, hoje)
    if hoje == "2026-05-10":
        assert s["data_fim"] == "2026-05-20"
        assert [i["data"] for i in s["itens"] if i["grupo"] == "vencida"] == ["2026-05-09"]
        assert [i["valor"] for i in s["itens"] if i["grupo"] == "vencida"] == ["800.00"]
        assert resumo(s, "fixos_pendentes", "receitas_pendentes", "compromissos", "alerta") == {
            "fixos_pendentes": "300.00",
            "receitas_pendentes": "50.00",
            "compromissos": "300.00",
            "alerta": False,
        }
    assert (s["fixos_pendentes"], s["receitas_pendentes"], s["disponivel"]) == (
        fixos,
        receitas,
        disponivel,
    )
    assert (s["sobra"], s["vencidas"]) == (sobra, vencidas)


# ------------------------------------------------------------------ horizonte com vigência


def test_horizonte_com_vigencia_f_r2_09(client: TestClient, usuario: Usuario) -> None:
    """SPEC-010-AC-9 e AC-13 (F-R2-09): horizonte 10 desde 01/01 e 20 desde 01/06. Fixos mensais
    (dia 5, 100,00; dia 20, 300,00) desde 2026-06, saldo zero. Em 31/05: horizonte 10, fim 10/06,
    compromissos 100,00. Em 01/06: horizonte 20, fim 21/06, compromissos 400,00."""
    c = Cenario(client, usuario, saldo="0.00")
    sem = r2_em(client, "2026-05-31")
    assert sem["horizonte_dias"] == 10  # sem parâmetro gravado
    c.recorrente("fixo_a", valor="100.00", dia=5, inicio="2026-06")
    c.recorrente("fixo_b", valor="300.00", dia=20, inicio="2026-06")
    assert c.horizonte(10, "2026-01-01").status_code == 200
    assert c.horizonte(20, "2026-06-01").status_code == 200

    s = r2_em(client, "2026-05-31")
    assert (s["horizonte_dias"], s["data_fim"], s["compromissos"]) == (10, "2026-06-10", "100.00")
    assert (s["sobra"], s["alerta"]) == ("-100.00", True)
    s = r2_em(client, "2026-06-01")
    assert (s["horizonte_dias"], s["data_fim"], s["compromissos"]) == (20, "2026-06-21", "400.00")
    assert (s["sobra"], s["alerta"]) == ("-400.00", True)


def test_horizonte_gravar_listar_e_idempotencia(client: TestClient, usuario: Usuario) -> None:
    """SPEC-010-AC-9 e AC-13: PUT grava (200) e é idempotente; a mesma vigência regravada vale a
    última; a listagem traz uma linha por `vigente_desde`, do mais antigo ao mais novo."""
    c = Cenario(client, usuario)
    assert client.get("/api/r2/horizonte").json() == []
    r = c.horizonte(15, "2026-06-01")
    assert r.status_code == 200 and r.json() == {"dias": 15, "vigente_desde": "2026-06-01"}
    assert c.horizonte(15, "2026-06-01").json() == r.json()
    assert c.horizonte(5, "2026-01-01").json() == {"dias": 5, "vigente_desde": "2026-01-01"}
    assert c.horizonte(30, "2026-06-01").json() == {"dias": 30, "vigente_desde": "2026-06-01"}
    assert client.get("/api/r2/horizonte").json() == [
        {"dias": 5, "vigente_desde": "2026-01-01"},
        {"dias": 30, "vigente_desde": "2026-06-01"},
    ]
    assert r2_em(client, "2026-06-01")["horizonte_dias"] == 30


@pytest.mark.parametrize(
    "campos",
    [{"dias": 0}, {"dias": 91}, {"dias": -1}, {"vigente_desde": "1999-12-31"}],
)
def test_horizonte_fora_dos_limites_e_ab422(
    client: TestClient, usuario: Usuario, campos: dict[str, Any]
) -> None:
    """SPEC-010-AC-9 e AC-13: horizonte fora de 1 a 90 e vigência antes de 2000 voltam 422 com
    X-Abako-Erro: AB422 e mensagem literal; nada é gravado."""
    csrf = logar(client, usuario)
    corpo = {"dias": 10, "vigente_desde": "2026-01-01", **campos}
    r = client.put("/api/r2/horizonte", json=corpo, headers=escrita(csrf))
    assert codigo(r) == (422, "AB422")
    assert isinstance(r.json()["detail"], str)
    assert "1999-12-31" not in r.text
    assert client.get("/api/r2/horizonte").json() == []


@pytest.mark.parametrize(
    "corpo",
    [
        {"dias": 10},
        {"vigente_desde": "2026-01-01"},
        {"dias": "dez", "vigente_desde": "2026-01-01"},
        {"dias": 10.5, "vigente_desde": "2026-01-01"},
        {"dias": 2**31, "vigente_desde": "2026-01-01"},
        {"dias": 10, "vigente_desde": "ontem"},
        {"dias": 10, "vigente_desde": "2026-01-01", "x": 1},
    ],
)
def test_horizonte_corpo_invalido_e_422_sem_eco(
    client: TestClient, usuario: Usuario, corpo: dict[str, Any]
) -> None:
    """SPEC-010-AC-13: corpo mal formado (float, chave desconhecida, inteiro acima do integer do
    banco) é 422 do contrato e o valor recebido não volta na resposta."""
    csrf = logar(client, usuario)
    r = client.put("/api/r2/horizonte", json=corpo, headers=escrita(csrf))
    assert r.status_code == 422, r.text
    assert all("input" not in erro for erro in r.json()["detail"])
    for valor in ("dez", "ontem", "10.5"):
        assert valor not in r.text


# ------------------------------------------------------------------ vencimento do cartão


def test_vencimento_gravar_listar_e_idempotencia(client: TestClient, usuario: Usuario) -> None:
    """SPEC-010-AC-6 e AC-13: PUT grava com vigência e é idempotente; regravar a mesma vigência vale
    o último; a listagem vem do mais antigo ao mais novo; dia e data fora do limite são AB422."""
    c = Cenario(client, usuario)
    cartao = c.cartao(fechamento=10, vencimento=None)
    url = f"/api/cartoes/{cartao}/vencimentos"
    assert client.get(url).json() == []
    r = c.vencimento(cartao, 20, "2026-01-01")
    assert r.status_code == 200 and r.json() == {"dia": 20, "vigente_desde": "2026-01-01"}
    assert c.vencimento(cartao, 20, "2026-01-01").json() == r.json()
    assert c.vencimento(cartao, 5, "2026-06-01").status_code == 200
    assert c.vencimento(cartao, 25, "2026-06-01").status_code == 200
    assert client.get(url).json() == [
        {"dia": 20, "vigente_desde": "2026-01-01"},
        {"dia": 25, "vigente_desde": "2026-06-01"},
    ]
    for dia, desde in ((0, "2026-01-01"), (32, "2026-01-01"), (10, "1999-12-31")):
        assert codigo(c.vencimento(cartao, dia, desde)) == (422, "AB422"), (dia, desde)
    assert len(client.get(url).json()) == 2


def test_vencimento_em_conta_que_nao_e_cartao_ou_inexistente_e_404(
    client: TestClient, usuario: Usuario
) -> None:
    """SPEC-010-AC-13: só cartão tem vencimento; conta corrente e id inexistente são 404."""
    c = Cenario(client, usuario)
    for conta in (c.corrente, 999_999_999):
        assert codigo(c.vencimento(conta, 10)) == (404, "AB404")
        assert client.get(f"/api/cartoes/{conta}/vencimentos").status_code == 404
    assert client.get("/api/cartoes/0/vencimentos").status_code == 422


@pytest.mark.parametrize(
    ("fechamento", "vencimento", "compra", "hoje", "vence"),
    [
        (10, 20, "2026-04-20", "2026-05-12", "2026-05-20"),  # V > F: vence no mês da competência
        (25, 5, "2026-03-30", "2026-04-25", "2026-05-05"),  # V <= F: no mês seguinte
        (10, 10, "2026-04-20", "2026-06-05", "2026-06-10"),  # V = F: no mês seguinte
        (10, 20, "2026-04-20", "2026-05-01", "2026-05-20"),  # vence depois de hoje + 10: fora
    ],
)
def test_vencimento_da_competencia_f_r2_06(
    client: TestClient,
    usuario: Usuario,
    fechamento: int,
    vencimento: int,
    compra: str,
    hoje: str,
    vence: str,
) -> None:
    """SPEC-010-AC-6 e AC-13 (F-R2-06): vence no mês M se vencimento > fechamento, senão em M+1.
    O horizonte de 10 dias só alcança a fatura se o vencimento calculado cair dentro dele."""
    c = Cenario(client, usuario, saldo="0.00")
    cartao = c.cartao(fechamento, vencimento)
    c.compra(cartao, compra, "100.00")
    # Uma sondagem por data: a fatura aparece com `data` = vencimento calculado pelo banco quando
    # ele cai dentro de [hoje, hoje + 10]; fora, não aparece.
    s = r2_em(client, hoje)
    datas = [i["data"] for i in s["itens"] if i["grupo"] == "fatura"]
    assert datas == ([vence] if vence <= s["data_fim"] else [])
    if datas:
        assert (s["faturas_proprias"], s["sobra"]) == ("100.00", "-100.00")
    else:
        assert (s["faturas_proprias"], s["sobra"]) == ("0.00", "0.00")


def test_vencimento_com_vigencia_f_r2_06(client: TestClient, usuario: Usuario) -> None:
    """SPEC-010-AC-6 e AC-13 (F-R2-06): fechamento 10; vencimento 20 desde 01/01 e 5 desde 01/06.
    A competência 2026-05 vence em 20/05; a 2026-06 (dia 5 vigente no último dia de junho, 5 <= 10)
    vence em 05/07."""
    c = Cenario(client, usuario, saldo="0.00")
    cartao = c.cartao(10, 20)
    assert c.vencimento(cartao, 5, "2026-06-01").status_code == 200
    c.compra(cartao, "2026-04-20", "100.00")  # competência 2026-05
    c.compra(cartao, "2026-05-20", "70.00")  # competência 2026-06
    s = r2_em(client, "2026-05-12")
    assert [(i["competencia"], i["data"], i["valor"]) for i in s["itens"]] == [
        ("2026-05", "2026-05-20", "100.00")
    ]
    s = r2_em(client, "2026-06-26")  # fim = 06/07
    assert [(i["competencia"], i["data"], i["valor"]) for i in s["itens"]] == [
        ("2026-06", "2026-07-05", "70.00")
    ]
    assert s["sobra"] == "-70.00"


def test_fatura_que_cruza_o_mes_f_r2_06(client: TestClient, usuario: Usuario) -> None:
    """SPEC-010-AC-6 e AC-13 (F-R2-06): fechamento 25 e vencimento 5; hoje 25/04, saldo 2000,00.
    A competência 2026-04 (900,00) vence em 05/05 = hoje + 10 e entra; a 2026-05 (500,00) vence em
    05/06 e fica fora. Compromissos 900,00; sobra 1100,00."""
    c = Cenario(client, usuario, saldo="2000.00")
    cartao = c.cartao(25, 5)
    c.compra(cartao, "2026-03-30", "900.00")
    c.compra(cartao, "2026-04-26", "500.00")
    s = r2_em(client, "2026-04-25")
    assert resumo(s, "faturas_proprias", "compromissos", "sobra") == {
        "faturas_proprias": "900.00",
        "compromissos": "900.00",
        "sobra": "1100.00",
    }
    assert [(i["competencia"], i["data"]) for i in s["itens"]] == [("2026-04", "2026-05-05")]


# ------------------------------------------------------------------ pagamento parcial e aberta


def test_pagamento_parcial_f_r2_07(client: TestClient, usuario: Usuario) -> None:
    """SPEC-010-AC-7 e AC-13 (F-R2-07, INV-18): hoje 10/05, saldo 3000,00, fechamento 10 e
    vencimento 20. Compras: 200,00 (competência abril), 1000,00 própria e 300,00 de pessoa
    (maio). Pago 450,00 em 30/04: quita os 200,00 de abril e 250,00 caem na própria de maio.
    Fatura de maio: total 1300,00, própria 1000,00; compromisso 1000,00 - 250,00 = 750,00; saldo
    2550,00; sobra 1800,00; fechada em 10/05, logo não parcial."""
    c = Cenario(client, usuario, saldo="3000.00")
    cartao = c.cartao(10, 20)
    pessoa = c.pessoa()
    c.compra(cartao, "2026-03-20", "200.00")
    c.compra(cartao, "2026-04-12", "1000.00")
    c.compra(cartao, "2026-04-15", "300.00", pessoa_id=pessoa)
    c.pagar(cartao, "2026-04-30", "450.00")

    maio = client.get(f"/api/cartoes/{cartao}/faturas/2026-05").json()
    assert (maio["total"], maio["propria"], maio["terceiros"]) == ("1300.00", "1000.00", "300.00")
    s = r2_em(client, "2026-05-10")
    assert resumo(s, "saldos_correntes", "faturas_proprias", "compromissos", "sobra") == {
        "saldos_correntes": "2550.00",
        "faturas_proprias": "750.00",
        "compromissos": "750.00",
        "sobra": "1800.00",
    }
    item = s["itens"][0]
    assert (item["valor"], item["bruto"], item["pago"], item["parcial"]) == (
        "750.00",
        "1000.00",
        "250.00",
        False,
    )
    assert len(s["itens"]) == 1


def test_fatura_aberta_aparece_como_parcial_f_r2_08(client: TestClient, usuario: Usuario) -> None:
    """SPEC-010-AC-7 e AC-13 (F-R2-08): hoje 08/05 (antes do fechamento no dia 10), fatura de
    600,00 vence em 15/05, saldo 1000,00: entra como parcial; sobra 400,00. Em 10/05 já não é."""
    c = Cenario(client, usuario, saldo="1000.00")
    cartao = c.cartao(10, 15)
    c.compra(cartao, "2026-04-20", "600.00")
    s = r2_em(client, "2026-05-08")
    assert resumo(s, "faturas_proprias", "compromissos", "sobra", "alerta") == {
        "faturas_proprias": "600.00",
        "compromissos": "600.00",
        "sobra": "400.00",
        "alerta": False,
    }
    assert [i["parcial"] for i in s["itens"]] == [True]
    assert [i["parcial"] for i in r2_em(client, "2026-05-10")["itens"]] == [False]


def test_cartao_sem_vencimento_vira_pendencia(client: TestClient, usuario: Usuario) -> None:
    """SPEC-010-AC-7 e AC-13: cartão com dívida e sem vencimento não entra na sobra e conta em
    `pendencias_vencimento`; gravar o vencimento resolve a pendência e a fatura entra."""
    c = Cenario(client, usuario, saldo="1000.00")
    cartao = c.cartao(10, None)
    c.compra(cartao, "2026-04-20", "100.00")
    s = r2_em(client, "2026-05-10")
    assert (s["pendencias_vencimento"], s["faturas_proprias"], s["sobra"]) == (
        1,
        "0.00",
        "1000.00",
    )
    assert s["itens"] == []
    assert c.vencimento(cartao, 20).status_code == 200
    s = r2_em(client, "2026-05-10")
    assert (s["pendencias_vencimento"], s["faturas_proprias"], s["sobra"]) == (
        0,
        "100.00",
        "900.00",
    )


# ------------------------------------------------------------------ hoje determinístico


@pytest.mark.parametrize(
    ("hoje", "fixos", "vencidas", "fim"),
    [
        ("2026-12-25", "0.00", 2, "2027-01-04"),  # 05/01 ainda fora (fim = 04/01)
        ("2026-12-26", "100.00", 2, "2027-01-05"),  # fim = 05/01: entra (virada de ano)
        ("2027-01-05", "100.00", 2, "2027-01-15"),  # hoje = dia do recorrente: entra
        ("2027-01-06", "0.00", 3, "2027-01-16"),  # 05/01 passou: vencida
    ],
)
def test_hoje_decide_na_virada_de_mes_e_de_ano(
    client: TestClient, usuario: Usuario, hoje: str, fixos: str, vencidas: int, fim: str
) -> None:
    """SPEC-010-AC-3 e AC-13: fixo de 100,00 todo dia 5 desde novembro/2026, horizonte 10. O dia
    de hoje e o de hoje + 10 entram; a ocorrência de janeiro entra a partir de 26/12; a de hoje -
    1 é vencida (nenhuma está vinculada, então novembro e dezembro já contam como vencidas)."""
    c = Cenario(client, usuario, saldo="0.00")
    c.recorrente("Fixo", valor="100.00", dia=5, inicio="2026-11")
    s = r2_em(client, hoje)
    assert (s["fixos_pendentes"], s["data_fim"], s["vencidas"]) == (fixos, fim, vencidas)


@pytest.mark.parametrize(
    ("utc", "fixos", "vencidas", "fim"),
    [
        (datetime(2027, 1, 1, 2, 30, tzinfo=UTC), "100.00", 0, "2027-01-10"),  # 31/12 23:30 SP
        (datetime(2027, 1, 1, 3, 30, tzinfo=UTC), "0.00", 1, "2027-01-11"),  # 01/01 00:30 SP
    ],
)
def test_hoje_usa_o_fuso_de_sao_paulo(
    client: TestClient,
    usuario: Usuario,
    monkeypatch: pytest.MonkeyPatch,
    utc: datetime,
    fixos: str,
    vencidas: int,
    fim: str,
) -> None:
    """SPEC-010-AC-13: o caminho de produção (sem override) decide pelo fuso, não por UTC. Fixo
    de 100,00 no dia 31 desde dezembro/2026: em 31/12 23:30 (SP) ele é de hoje; em 01/01 00:30 (SP)
    já é vencido."""
    c = Cenario(client, usuario, saldo="0.00")
    c.recorrente("Fixo", valor="100.00", dia=31, inicio="2026-12")

    class RelogioFalso(datetime):
        @classmethod
        def now(cls, tz: Any = None) -> RelogioFalso:
            return cls.fromtimestamp(utc.timestamp(), tz)

    monkeypatch.setattr(svc_data, "datetime", RelogioFalso)
    r = client.get("/api/r2")
    assert r.status_code == 200, r.text
    s = r.json()
    assert (s["fixos_pendentes"], s["vencidas"], s["data_fim"]) == (fixos, vencidas, fim)


def test_hoje_e_user_id_nao_vem_do_cliente(client: TestClient, usuario: Usuario) -> None:
    """SPEC-010-AC-13: `hoje` e `user_id` na query são ignorados."""
    Cenario(client, usuario, saldo="100.00")
    with hoje_em(client, "2026-05-10"):
        r = client.get("/api/r2", params={"hoje": "1999-01-01", "user_id": 1})
    assert r.status_code == 200 and r.json()["data_fim"] == "2026-05-20"
    assert r.json()["saldos_correntes"] == "100.00"


# ------------------------------------------------------------------ sessão, CSRF, isolamento


def test_sem_sessao_e_401(client: TestClient) -> None:
    """SPEC-010-AC-13: as rotas do R2, do horizonte e do vencimento exigem sessão."""
    for url in ("/api/r2", "/api/r2/horizonte", "/api/cartoes/1/vencimentos"):
        assert client.get(url).status_code == 401, url
    horizonte = {"dias": 10, "vigente_desde": "2026-01-01"}
    assert client.put("/api/r2/horizonte", json=horizonte, headers=ORIGEM).status_code == 401
    venc = {"dia": 10, "vigente_desde": "2026-01-01"}
    assert client.put("/api/cartoes/1/vencimentos", json=venc, headers=ORIGEM).status_code == 401


def test_escrita_sem_csrf_e_403(client: TestClient, usuario: Usuario) -> None:
    """SPEC-010-AC-13: sem token CSRF (ou errado) o horizonte e o vencimento não gravam."""
    c = Cenario(client, usuario)
    cartao = c.cartao(10, None)
    errado = {**ORIGEM, "X-CSRF-Token": "errado"}
    horizonte = {"dias": 10, "vigente_desde": "2026-01-01"}
    venc = {"dia": 10, "vigente_desde": "2026-01-01"}
    for cab in (ORIGEM, errado):
        assert client.put("/api/r2/horizonte", json=horizonte, headers=cab).status_code == 403
        r = client.put(f"/api/cartoes/{cartao}/vencimentos", json=venc, headers=cab)
        assert r.status_code == 403
    assert client.get("/api/r2/horizonte").json() == []
    assert client.get(f"/api/cartoes/{cartao}/vencimentos").json() == []


def test_user_id_no_corpo_e_descartado(
    client: TestClient, usuario: Usuario, outro_usuario: Usuario
) -> None:
    """SPEC-010-AC-13 (INV-13): `user_id` no corpo não grava para o outro usuário."""
    c = Cenario(client, usuario)
    cartao = c.cartao(10, None)
    corpo = {"dias": 12, "vigente_desde": "2026-01-01", "user_id": outro_usuario.user_id}
    assert client.put("/api/r2/horizonte", json=corpo, headers=escrita(c.csrf)).status_code == 200
    corpo = {"dia": 12, "vigente_desde": "2026-01-01", "user_id": outro_usuario.user_id}
    url = f"/api/cartoes/{cartao}/vencimentos"
    assert client.put(url, json=corpo, headers=escrita(c.csrf)).status_code == 200
    client.post("/api/auth/logout", headers=escrita(c.csrf))
    client.cookies.clear()
    logar(client, outro_usuario)
    assert client.get("/api/r2/horizonte").json() == []


def test_isolamento_entre_usuarios(
    client: TestClient, usuario: Usuario, outro_usuario: Usuario
) -> None:
    """SPEC-010-AC-11 e AC-13 (INV-13): o outro usuário vê a situação vazia, nenhum horizonte, e o
    cartão do dono é 404 (leitura e escrita); o horizonte dele não altera o do dono."""
    c = Cenario(client, usuario, saldo="5000.00")
    c.recorrente("Aluguel", valor="2500.00", dia=12, fim="2026-05")
    cartao = c.cartao(10, 20)
    c.compra(cartao, "2026-04-20", "4200.00")
    assert c.horizonte(30).status_code == 200
    assert r2_em(client, "2026-05-10")["horizonte_dias"] == 30
    client.post("/api/auth/logout", headers=escrita(c.csrf))
    client.cookies.clear()

    o = Cenario(client, outro_usuario, saldo=None)
    s = r2_em(client, "2026-05-10")
    assert resumo(s, *TOTAIS) == {
        "saldos_correntes": "0.00",
        "receitas_pendentes": "0.00",
        "disponivel": "0.00",
        "fixos_pendentes": "0.00",
        "faturas_proprias": "0.00",
        "compromissos": "0.00",
        "sobra": "0.00",
        "alerta": False,
    }
    assert (s["horizonte_dias"], s["itens"], s["vencidas"], s["pendencias_vencimento"]) == (
        10,
        [],
        0,
        0,
    )
    assert client.get("/api/r2/horizonte", params={"user_id": usuario.user_id}).json() == []
    assert client.get(f"/api/cartoes/{cartao}/vencimentos").status_code == 404
    assert codigo(o.vencimento(cartao, 15)) == (404, "AB404")
    assert o.horizonte(5).status_code == 200

    client.post("/api/auth/logout", headers=escrita(o.csrf))
    client.cookies.clear()
    logar(client, usuario)
    assert client.get("/api/r2/horizonte").json() == [{"dias": 30, "vigente_desde": "2026-01-01"}]
    assert client.get(f"/api/cartoes/{cartao}/vencimentos").json() == [
        {"dia": 20, "vigente_desde": "2026-01-01"}
    ]


# ------------------------------------------------------------------ log e métodos


def test_valores_e_nome_fora_do_log(
    client: TestClient, usuario: Usuario, caplog: pytest.LogCaptureFixture
) -> None:
    """SPEC-010-AC-13: nenhum valor financeiro nem o nome do recorrente vai a log, na situação,
    no horizonte e no vencimento."""
    c = Cenario(client, usuario, saldo="5123.45")
    cartao = c.cartao(10, 20)
    with caplog.at_level(logging.DEBUG):
        c.recorrente("Nome-Sigiloso-RR", valor="2345.67", dia=12, fim="2026-05")
        c.compra(cartao, "2026-04-20", "3456.78")
        c.horizonte(11)
        c.vencimento(cartao, 21)
        s = r2_em(client, "2026-05-10")
        client.get("/api/r2/horizonte")
        client.get(f"/api/cartoes/{cartao}/vencimentos")
    assert (s["fixos_pendentes"], s["compromissos"], s["sobra"]) == (
        "2345.67",
        "5802.45",
        "-679.00",
    )
    for texto in ("Nome-Sigiloso-RR", "5123.45", "2345.67", "3456.78", "5802.45", "679.00"):
        assert texto not in caplog.text


def test_metodos_nao_previstos(client: TestClient, usuario: Usuario) -> None:
    """A situação é só GET; o horizonte e o vencimento, só GET e PUT."""
    csrf = logar(client, usuario)
    for metodo in ("post", "put", "delete"):
        assert getattr(client, metodo)("/api/r2", headers=escrita(csrf)).status_code == 405, metodo
    for metodo in ("post", "delete"):
        r = getattr(client, metodo)("/api/r2/horizonte", headers=escrita(csrf))
        assert r.status_code == 405, metodo
        r = getattr(client, metodo)("/api/cartoes/1/vencimentos", headers=escrita(csrf))
        assert r.status_code == 405, metodo
