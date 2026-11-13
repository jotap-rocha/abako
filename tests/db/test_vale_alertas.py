"""SPEC-013 / ADR 052: alerta R5 (resta de um bolso do VR negativo no mês corrente)."""

from __future__ import annotations

from decimal import Decimal
from typing import Any

import psycopg
import pytest

from tests.db.util_alertas import alertas, de
from tests.db.util_saldo import dec, fixture, novo_usuario
from tests.db.util_vale import decidir, mes_do_vale, novo_vale

pytestmark = pytest.mark.banco


def _r5(conn: psycopg.Connection, uid: int, hoje: str) -> list[dict[str, Any]]:
    return de(alertas(conn, uid, hoje), "R5")


def test_f_vale_08_r5_duplo(conn: psycopg.Connection) -> None:
    f = fixture("F-VALE-08")
    e = f["entrada"]
    v = novo_vale(conn, base=e["base_trabalho"])
    mes_do_vale(conn, v, "2025-05", e["credito"], e["consumo"]["trabalho"], e["consumo"]["pessoal"])
    itens = _r5(conn, v.uid, "2025-05-20")
    esperados = f["esperado"]["alertas"]
    assert len(itens) == len(esperados) == 2
    for item, esp in zip(itens, esperados, strict=True):
        assert (item["codigo"], item["tipo"], item["severidade"], item["detalhe"]) == (
            esp["codigo"], esp["tipo"], esp["severidade"], esp["detalhe"],
        )  # fmt: skip
        assert item["bolso"] == esp["bolso"]
        assert item["alocacao"] == dec(esp["alocacao"])
        assert item["consumo"] == dec(esp["consumo"])
        assert item["resta"] == dec(esp["resta"]) == Decimal("-50.00")
        assert item["conta_id"] == v.vr and item["mes"] == "2025-05"
        assert not any(ch.isdigit() for ch in item["mensagem"])  # mensagem literal, sem valores
    # a sobra do mês é 0.00: nenhum bolso sobra para compensar o outro
    assert dec(f["esperado"]["sobra"]) == Decimal("0.00")
    # ordenação geral: alta antes de baixa (a configuração da reserva pendente vem depois)
    codigos = [a["codigo"] for a in alertas(conn, v.uid, "2025-05-20")]
    assert codigos == ["R5", "R5", "CONFIG"]


def test_r5_sem_compensacao_f_vale_03(conn: psycopg.Connection) -> None:
    f = fixture("F-VALE-03")
    e = f["entrada"]
    v = novo_vale(conn, base=e["base_trabalho"])
    mes_do_vale(
        conn, v, "2025-05", e["credito_mes"], e["consumo"]["trabalho"], e["consumo"]["pessoal"]
    )
    itens = _r5(conn, v.uid, "2025-05-20")
    # trabalho estourado (−50.00) dispara mesmo havendo sobra de 100.00 no pessoal
    assert [(a["detalhe"], a["resta"]) for a in itens] == [
        ("vale_trabalho_estourado", dec(f["esperado"]["resta"]["trabalho"]))
    ]
    assert f["esperado"]["alerta_trabalho"] is True


def test_resta_zero_nao_dispara(conn: psycopg.Connection) -> None:
    v = novo_vale(conn)
    mes_do_vale(conn, v, "2025-05", "1000.00", "200.00", "800.00")  # resta 0.00/0.00
    assert _r5(conn, v.uid, "2025-05-20") == []
    mes_do_vale(conn, v, "2025-06", "1000.00", "200.01", "0.00")  # um centavo acima
    assert [a["resta"] for a in _r5(conn, v.uid, "2025-06-20")] == [Decimal("-0.01")]


def test_f_vale_11_r5_so_no_mes_corrente(conn: psycopg.Connection) -> None:
    f = fixture("F-VALE-11")
    e = f["entrada"]
    v = novo_vale(conn, base=e["base_trabalho"])
    for mes, m in e["meses"].items():
        mes_do_vale(conn, v, mes, m["credito"], m["consumo"]["trabalho"], m["consumo"]["pessoal"])
    for hoje, chave in (
        ("2025-05-20", "hoje_2025-05-20"),
        ("2025-06-15", "hoje_2025-06-15"),
        ("2025-07-05", "hoje_2025-07-05"),
    ):
        esperados = f["esperado"][chave]["alertas"]
        itens = _r5(conn, v.uid, hoje)
        assert [(a["detalhe"], a["resta"]) for a in itens] == [
            (x["detalhe"], dec(x["resta"])) for x in esperados
        ], hoje
        assert all(a["mes"] == hoje[:7] for a in itens)


def test_r5_sem_credito_nao_dispara(conn: psycopg.Connection) -> None:
    """F-VALE-06 (mes_sem_credito): resta pessoal −30.00, mas sem crédito não há R5."""
    caso = next(c for c in fixture("F-VALE-06")["casos"] if c["nome"] == "mes_sem_credito")
    e = caso["entrada"]
    v = novo_vale(conn, base=e["base_trabalho"])
    mes_do_vale(conn, v, "2025-05", e["credito"], e["consumo"]["trabalho"], e["consumo"]["pessoal"])
    assert caso["esperado"]["r5"] is False
    assert _r5(conn, v.uid, "2025-05-20") == []
    # sem parâmetro do vale (sem_conta) também não há R5
    assert _r5(conn, novo_usuario(conn), "2025-05-20") == []


def test_r5_considera_o_ajuste_decidido(conn: psycopg.Connection) -> None:
    v = novo_vale(conn)
    mes_do_vale(conn, v, "2025-05", "1000.00", "250.00", "700.00")  # sobra 100.00 (F-VALE-03)
    mes_do_vale(conn, v, "2025-06", "1000.00", "220.00", "0.00")
    assert [a["resta"] for a in _r5(conn, v.uid, "2025-06-15")] == [Decimal("-20.00")]
    decidir(conn, v.uid, "2025-05", "trabalho")  # trabalho de junho: 200.00 + 100.00 = 300.00
    assert _r5(conn, v.uid, "2025-06-15") == []
    decidir(conn, v.uid, "2025-05", "pessoal")  # a decisão trocada tira o ajuste do trabalho
    assert [a["resta"] for a in _r5(conn, v.uid, "2025-06-15")] == [Decimal("-20.00")]


def test_r5_isolamento_por_user_id(conn: psycopg.Connection) -> None:
    a = novo_vale(conn)
    mes_do_vale(conn, a, "2025-05", "1000.00", "250.00", "850.00")
    b = novo_vale(conn)
    mes_do_vale(conn, b, "2025-05", "1000.00", "10.00", "10.00")
    assert len(_r5(conn, a.uid, "2025-05-20")) == 2
    assert _r5(conn, b.uid, "2025-05-20") == []
    assert all(x["conta_id"] == a.vr for x in _r5(conn, a.uid, "2025-05-20"))
    assert _r5(conn, novo_usuario(conn), "2025-05-20") == []
