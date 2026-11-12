"""SPEC-009 / ADR 047: reserva, cobertura, níveis, aporte e parâmetros com vigência.

Esperados de F-RES-01 a F-RES-08 (fixtures/numericos.yaml), calculados à mão.
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal
from typing import Any

import psycopg
import pytest

from tests.db.util_lancamento import Recusa, conta, excluir, lancar
from tests.db.util_reserva import d, nova_reserva, parametro, situacao
from tests.db.util_saldo import dec, dia, fixture, novo_usuario, snapshot

pytestmark = pytest.mark.banco


def _cenario(
    conn: psycopg.Connection,
    saldo: str,
    *,
    meses: int = 3,
    gasto: str = "4000.00",
    alvo: str | None = None,
) -> int:
    """Usuário com uma reserva de saldo inicial `saldo` (snapshot em 2026-01-01) e parâmetros."""
    uid = novo_usuario(conn)
    nova_reserva(conn, uid, "caixinha", {"data": "2026-01-01", "valor": saldo})
    parametro(conn, uid, desde="2026-01-01", meses=meses, gasto=gasto, alvo=alvo)
    return uid


def test_cobertura(conn: psycopg.Connection) -> None:
    """AC-1 / INV-12: cobertura = saldo líquido ÷ gasto essencial (F-RES-02, F-RES-06)."""
    f2 = fixture("F-RES-02")
    entrada, esperado = f2["entrada"], f2["esperado"]
    uid = _cenario(conn, entrada["saldo_reserva"], gasto=entrada["gasto_essencial"])
    s = situacao(conn, uid, "2026-04-01")
    assert s["cobertura_meses"] == dec(esperado["cobertura_meses"])
    assert str(s["cobertura_meses"]) == esperado["cobertura_meses"]  # duas casas, texto
    assert s["meses_meta"] == esperado["meta_meses"]
    assert s["nivel"] == esperado["nivel"]
    assert s["config_pendente"] is False

    # não exata: 2 casas, meio-para-cima (F-RES-06), de ponta a ponta e na função pura
    for caso in fixture("F-RES-06")["casos"]:
        uid = _cenario(conn, caso["saldo"], gasto=caso["gasto_essencial"])
        assert str(situacao(conn, uid, "2026-04-01")["cobertura_meses"]) == caso["cobertura_meses"]
        linha = conn.execute(
            "SELECT reserva_cobertura(%s, %s)", (dec(caso["saldo"]), dec(caso["gasto_essencial"]))
        ).fetchone()
        assert linha == (dec(caso["cobertura_meses"]),)


def test_cortes_nivel(conn: psycopg.Connection) -> None:
    """AC-2 / INV-17: níveis mudam exatamente em 50% e 100% da meta (F-RES-01, meta 12000.00)."""
    f = fixture("F-RES-01")
    assert f["entrada"]["meta"] == "12000.00"
    for caso in f["casos"]:
        uid = _cenario(conn, caso["saldo"])  # 3 x 4000.00 = 12000.00
        s = situacao(conn, uid, "2026-04-01")
        assert s["meta"] == dec(f["entrada"]["meta"])
        assert s["nivel"] == caso["nivel"], caso
        if "falta" in caso:
            assert s["falta"] == dec(caso["falta"]), caso


def test_aporte_mensal(conn: psycopg.Connection) -> None:
    """AC-3: aporte até a data-alvo (F-RES-01 exato; F-RES-05 não exato, mês igual, passada)."""
    f1 = fixture("F-RES-01")["aporte_mensal_ate_data_alvo"]
    uid = _cenario(conn, f1["saldo"], alvo="2026-10-20")  # abril -> outubro = 6 meses
    s = situacao(conn, uid, "2026-04-15")
    assert s["meses_ate_alvo"] == f1["meses_ate_alvo"]
    assert s["aporte_mensal"] == dec(f1["aporte"])

    f5 = fixture("F-RES-05")
    assert f5["entrada"]["parametros"] == {"meses": 3, "gasto_essencial": "4000.00"}
    for caso in f5["casos"]:
        uid = _cenario(conn, caso["saldo"], alvo=caso["data_alvo"])
        s = situacao(conn, uid, f5["entrada"]["hoje"])
        assert s["falta"] == dec(caso["falta"]), caso
        assert s["aporte_mensal"] == d(caso["aporte"]), caso
        assert s["alvo_vencida"] is caso.get("alvo_vencida", False), caso
        if "meses_ate_alvo" in caso:
            assert s["meses_ate_alvo"] == caso["meses_ate_alvo"], caso
        if caso["aporte"] is not None:
            assert str(s["aporte_mensal"]) == caso["aporte"]  # duas casas

    # sem data-alvo não há aporte (só a falta)
    uid = _cenario(conn, "3000.00")
    s = situacao(conn, uid, "2026-04-15")
    assert s["aporte_mensal"] is None and s["meses_ate_alvo"] is None and s["data_alvo"] is None
    assert s["falta"] == dec("9000.00")


def test_bruto_liquido_f_res_03(conn: psycopg.Connection) -> None:
    """AC-4 / INV-37 / INV-36: líquido, imposto acumulado e bruto; a cobertura usa o líquido."""
    f = fixture("F-RES-03")
    entrada, esperado = f["entrada"], f["esperado"]
    uid = novo_usuario(conn)
    r = entrada["reserva"]
    c = nova_reserva(conn, uid, "caixinha", r["snapshot"], r["rendimentos"])
    # ignorados: rendimento excluído (logicamente) e rendimento em conta de investimento
    exc = entrada["ignorados"][0]["rendimento_excluido"]
    tid, versao, _ = lancar(
        conn, uid, "rendimento", "2026-03-20", c, bruto=exc["bruto"], imposto=exc["imposto"]
    )
    excluir(conn, uid, tid, versao)
    inv = entrada["ignorados"][1]["rendimento"]
    invest = nova_reserva(conn, uid, "aplicacao", None, tipo="investimento")
    lancar(
        conn, uid, "rendimento", "2026-03-20", invest, bruto=inv["bruto"], imposto=inv["imposto"]
    )
    p = entrada["parametros"]
    parametro(conn, uid, desde=p["desde"], meses=p["meses"], gasto=p["gasto_essencial"])

    s = situacao(conn, uid, entrada["hoje"])
    assert s["saldo_liquido"] == dec(esperado["saldo_liquido"])
    assert s["imposto_acumulado"] == dec(esperado["imposto_acumulado"])
    assert s["saldo_bruto"] == dec(esperado["saldo_bruto"])
    assert s["saldo_bruto"] == s["saldo_liquido"] + s["imposto_acumulado"]
    assert s["meta"] == dec(esperado["meta"])
    assert s["nivel"] == esperado["nivel"]
    assert s["falta"] == dec(esperado["falta"])
    assert s["cobertura_meses"] == dec(esperado["cobertura_meses"])  # sobre o líquido
    assert s["cobertura_meses"] != dec(esperado["cobertura_se_usasse_bruto"])


def test_imposto_de_rendimento_futuro_nao_entra(conn: psycopg.Connection) -> None:
    """O imposto acumulado vai só até a data "hoje" informada."""
    f = fixture("F-RES-03")
    uid = novo_usuario(conn)
    r = f["entrada"]["reserva"]
    nova_reserva(conn, uid, "caixinha", r["snapshot"], r["rendimentos"])
    s = situacao(conn, uid, "2026-02-28")  # só o primeiro rendimento (10/02)
    assert s["imposto_acumulado"] == dec("22.50")
    assert s["saldo_liquido"] == dec("5077.50")
    assert s["saldo_bruto"] == dec("5100.00")


def test_soma_de_reservas_f_res_04(conn: psycopg.Connection) -> None:
    """AC-5: várias caixinhas somam; investimento fica fora; nível sobre a soma."""
    f = fixture("F-RES-04")
    entrada, esperado = f["entrada"], f["esperado"]
    uid = novo_usuario(conn)
    for item in entrada["reservas"]:
        nova_reserva(conn, uid, item["nome"], item["snapshot"], item.get("rendimentos"))
    inv = entrada["investimento"]["snapshot"]
    nova_reserva(conn, uid, "aplicacao", inv, tipo="investimento")
    p = entrada["parametros"]
    parametro(conn, uid, desde=p["desde"], meses=p["meses"], gasto=p["gasto_essencial"])

    s = situacao(conn, uid, entrada["hoje"])
    assert s["contas_reserva"] == esperado["contas_reserva"]
    assert s["saldo_liquido"] == dec(esperado["saldo_liquido"])
    assert s["imposto_acumulado"] == dec(esperado["imposto_acumulado"])
    assert s["saldo_bruto"] == dec(esperado["saldo_bruto"])
    assert s["meta"] == dec(esperado["meta"])
    assert s["nivel"] == esperado["nivel"]
    assert s["falta"] == dec(esperado["falta"])
    assert s["cobertura_meses"] == dec(esperado["cobertura_meses"])


def test_conta_que_deixa_de_ser_reserva_sai_da_soma_com_o_imposto(
    conn: psycopg.Connection,
) -> None:
    """O tipo VIGENTE da conta na consulta decide (ADR 047): saldo e imposto saem juntos."""
    f = fixture("F-RES-04")
    entrada, depois = f["entrada"], f["troca_de_tipo"]
    uid = novo_usuario(conn)
    contas = {}
    for item in entrada["reservas"]:
        contas[item["nome"]] = nova_reserva(
            conn, uid, item["nome"], item["snapshot"], item.get("rendimentos")
        )
    p = entrada["parametros"]
    parametro(conn, uid, desde=p["desde"], meses=p["meses"], gasto=p["gasto_essencial"])
    antes = situacao(conn, uid, entrada["hoje"])
    assert antes["saldo_liquido"] == dec("6577.50") and antes["imposto_acumulado"] == dec("22.50")

    b = contas["caixinha_b"]
    versao = conn.execute(
        "SELECT versao FROM conta_versao WHERE user_id = %s AND conta_id = %s AND vigente",
        (uid, b),
    ).fetchone()
    assert versao is not None
    conn.execute(
        "SELECT * FROM conta_gravar(%s, %s, %s, 'caixinha_b', 'investimento', NULL)",
        (uid, b, versao[0]),
    )
    s = situacao(conn, uid, entrada["hoje"])
    assert s["saldo_liquido"] == dec(depois["saldo_liquido"])
    assert s["imposto_acumulado"] == dec(depois["imposto_acumulado"])  # o imposto sai junto
    assert s["saldo_bruto"] == dec(depois["saldo_bruto"])
    assert s["contas_reserva"] == depois["contas_reserva"]


def test_parametros_com_vigencia_f_res_08(conn: psycopg.Connection) -> None:
    """AC-6: vale o maior `desde` não posterior a hoje; no mesmo `desde`, o último gravado."""
    f = fixture("F-RES-08")
    uid = novo_usuario(conn)
    nova_reserva(conn, uid, "caixinha", f["entrada"]["reserva"]["snapshot"])
    for p in f["entrada"]["parametros"]:
        parametro(conn, uid, desde=p["desde"], meses=p["meses"], gasto=p["gasto_essencial"])

    for caso in f["casos"]:
        s = situacao(conn, uid, caso["hoje"])
        assert s["config_pendente"] is caso.get("config_pendente", False), caso
        for chave in ("meta", "cobertura_meses", "falta"):
            if chave in caso:
                assert s[chave] == dec(caso[chave]), (chave, caso)
        if "nivel" in caso:
            assert s["nivel"] == caso["nivel"], caso

    # mesma vigência regravada: vale o último
    re = f["regravado"]
    p = re["parametro"]
    parametro(conn, uid, desde=p["desde"], meses=p["meses"], gasto=p["gasto_essencial"])
    s = situacao(conn, uid, re["caso"]["hoje"])
    assert s["meta"] == dec(re["caso"]["meta"])
    assert s["cobertura_meses"] == dec(re["caso"]["cobertura_meses"])
    # o histórico não foi reescrito: 3 registros (2 originais + a regravação)
    linha = conn.execute(
        "SELECT count(*) FROM reserva_parametro WHERE user_id = %s", (uid,)
    ).fetchone()
    assert linha == (3,)


def test_gravar_parametro_e_idempotente_e_futuro_vale_so_depois(conn: psycopg.Connection) -> None:
    uid = novo_usuario(conn)
    nova_reserva(conn, uid, "caixinha", {"data": "2026-01-01", "valor": "1000.00"})
    a = parametro(conn, uid, desde="2026-01-01", meses=3, gasto="1000.00", alvo="2027-01-01")
    b = parametro(conn, uid, desde="2026-01-01", meses=3, gasto="1000.00", alvo="2027-01-01")
    assert a == b  # repetir não cresce o histórico
    c = parametro(conn, uid, desde="2026-01-01", meses=3, gasto="1000.00")  # sem alvo: outro valor
    assert c != a
    assert situacao(conn, uid, "2026-02-01")["data_alvo"] is None  # o último gravado vale
    parametro(conn, uid, desde="2030-01-01", meses=6, gasto="9000.00")  # futuro
    assert situacao(conn, uid, "2026-02-01")["meses_meta"] == 3
    assert situacao(conn, uid, "2030-01-01")["meses_meta"] == 6


def test_validacao_dos_parametros(conn: psycopg.Connection) -> None:
    uid = novo_usuario(conn)
    ruins: list[tuple[Any, ...]] = [
        (uid, 0, dec("100.00"), None, dia("2026-01-01")),
        (uid, 121, dec("100.00"), None, dia("2026-01-01")),
        (uid, None, dec("100.00"), None, dia("2026-01-01")),
        (uid, 3, dec("-0.01"), None, dia("2026-01-01")),
        (uid, 3, dec("10.005"), None, dia("2026-01-01")),
        (uid, 3, None, None, dia("2026-01-01")),
        (uid, 3, dec("1000000000.00"), None, dia("2026-01-01")),
        (uid, 3, dec("100.00"), None, None),
        (uid, 3, dec("100.00"), None, dia("1999-12-31")),
        (uid, 3, dec("100.00"), dia("1999-12-31"), dia("2026-01-01")),
    ]
    for args in ruins:
        with Recusa(conn, "AB422"):
            conn.execute("SELECT reserva_parametro_gravar(%s, %s, %s, %s, %s)", args)
    with Recusa(conn, "AB404"):  # usuário inexistente
        conn.execute(
            "SELECT reserva_parametro_gravar(%s, 3, 100.00, NULL, DATE '2026-01-01')",
            (-1,),
        )
    with Recusa(conn, "AB422"):
        conn.execute("SELECT * FROM reserva_situacao(%s, NULL)", (uid,))
    # limites aceitos: 1 e 120 meses, gasto zero, data-alvo passada
    parametro(conn, uid, desde="2026-01-01", meses=1, gasto="0.00", alvo="2000-01-01")
    parametro(conn, uid, desde="2026-02-01", meses=120, gasto="999999999.99")


def test_config_ausente_f_res_07(conn: psycopg.Connection) -> None:
    """AC-7: gasto essencial ausente ou zero = configuração pendente, não alerta R1."""
    f = fixture("F-RES-07")
    entrada, esperado = f["entrada"], f["esperado"]

    def confere(uid: int) -> None:
        s = situacao(conn, uid, entrada["hoje"])
        assert s["saldo_liquido"] == dec(esperado["saldo_liquido"])
        assert s["saldo_bruto"] == dec(esperado["saldo_liquido"])
        assert s["meses_meta"] == esperado["meses_meta"]
        assert s["config_pendente"] is esperado["config_pendente"]
        for chave in ("cobertura_meses", "meta", "nivel", "falta", "aporte_mensal"):
            assert s[chave] is None, chave  # nada de nível crítico por falta de configuração

    sem = novo_usuario(conn)
    nova_reserva(conn, sem, "caixinha", entrada["reserva"]["snapshot"])
    confere(sem)  # nunca informado
    zero = novo_usuario(conn)
    nova_reserva(conn, zero, "caixinha", entrada["reserva"]["snapshot"])
    parametro(conn, zero, desde="2026-01-01", meses=3, gasto="0.00", alvo="2026-12-01")
    confere(zero)  # zero, mesmo com data-alvo
    assert situacao(conn, zero, entrada["hoje"])["data_alvo"] == date(2026, 12, 1)


def test_usuario_sem_reserva_tem_saldo_zero(conn: psycopg.Connection) -> None:
    uid = novo_usuario(conn)
    parametro(conn, uid, desde="2026-01-01", meses=3, gasto="1000.00")
    s = situacao(conn, uid, "2026-04-01")
    assert s["contas_reserva"] == 0
    assert s["saldo_liquido"] == s["saldo_bruto"] == Decimal("0.00")
    assert s["nivel"] == "critica" and s["falta"] == dec("3000.00")


def test_isolamento_por_user_id(conn: psycopg.Connection) -> None:
    """AC-8 / INV-13: o user_id de outro usuário não enxerga reserva nem parâmetros."""
    f = fixture("F-RES-03")
    dono = novo_usuario(conn)
    r = f["entrada"]["reserva"]
    nova_reserva(conn, dono, "caixinha", r["snapshot"], r["rendimentos"])
    p = f["entrada"]["parametros"]
    parametro(conn, dono, desde=p["desde"], meses=p["meses"], gasto=p["gasto_essencial"])

    outro = novo_usuario(conn)
    s = situacao(conn, outro, f["entrada"]["hoje"])
    assert s["contas_reserva"] == 0
    assert s["saldo_liquido"] == s["imposto_acumulado"] == s["saldo_bruto"] == dec("0.00")
    assert s["config_pendente"] is True  # os parâmetros do dono não vazam
    assert s["gasto_essencial"] is None and s["meta"] is None and s["nivel"] is None
    # e o do dono continua o mesmo
    assert situacao(conn, dono, f["entrada"]["hoje"])["saldo_liquido"] == dec("5139.50")
    # a view de parâmetros também é por usuário
    linha = conn.execute(
        "SELECT count(*) FROM reserva_parametro_vigente WHERE user_id = %s", (outro,)
    ).fetchone()
    assert linha == (0,)


def test_aporte_e_rendimento_nao_sao_receita_nem_despesa(conn: psycopg.Connection) -> None:
    """INV-12: guardar na reserva (transferência) e render não mexem em gasto real nem receita."""
    uid = novo_usuario(conn)
    corrente = conta(conn, uid, "corrente")
    snapshot(conn, uid, corrente, "2026-01-01", "1000.00")
    res = conta(conn, uid, "caixinha", "reserva", mae=corrente)
    lancar(conn, uid, "transferencia", "2026-02-05", corrente, "300.00", destino=res)
    lancar(conn, uid, "rendimento", "2026-02-10", res, bruto="10.00", imposto="2.00")
    mes = "2026-02"
    gasto = conn.execute("SELECT gasto_real(%s, %s)", (uid, mes)).fetchone()
    caixa = conn.execute("SELECT receita_caixa(%s, %s)", (uid, mes)).fetchone()
    assert gasto == (dec("0.00"),) and caixa == (dec("0.00"),)
    s = situacao(conn, uid, "2026-04-01")
    assert s["saldo_liquido"] == dec("308.00")  # 300.00 + (10.00 - 2.00)
    assert s["imposto_acumulado"] == dec("2.00")
