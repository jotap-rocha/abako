"""SPEC-010 / ADR 048: sobra do R2, horizonte, vencimento do cartão e fatura própria.

Esperados de F-R2-01 a F-R2-09 (fixtures/numericos.yaml), calculados à mão.
"""

from __future__ import annotations

from datetime import date
from typing import Any

import psycopg
import pytest

from tests.db.util_lancamento import Recusa, cartao, compra, conta, lancar, linha_credito
from tests.db.util_r2 import (
    definir_horizonte,
    definir_vencimento,
    desvincular,
    fechamento_da_fatura,
    itens,
    novo_cartao,
    ocorrencias,
    recorrente,
    situacao,
    usuario_com_corrente,
    vencimento,
    vincular,
)
from tests.db.util_saldo import dec, dia, fixture, novo_usuario, snapshot
from tests.db.util_terceiros import nova_pessoa, resumo_fatura

pytestmark = pytest.mark.banco

HOJE = "2026-05-10"


def _basico(
    conn: psycopg.Connection,
    entrada: dict[str, Any],
    fatura_propria: str,
    *,
    terceiros: str | None = None,
) -> tuple[int, int, int]:
    """Cenário de F-R2-01..03: saldo, receita (dia 15), fixo (dia 12) e uma fatura que vence em
    20/05 (cartão com fechamento 10 e vencimento 20; a compra de 20/04 cai na competência 2026-05).
    """
    uid, corrente = usuario_com_corrente(conn, entrada["saldos_correntes"])
    recorrente(
        conn,
        uid,
        "salario",
        "receita",
        entrada["receita_recorrente_pendente"],
        15,
        corrente,
        "2026-05",
    )
    recorrente(conn, uid, "aluguel", "fixo", entrada["fixos_pendentes"], 12, corrente, "2026-05")
    cartao_id = novo_cartao(conn, uid, 10, 20)
    compra(conn, uid, cartao_id, "2026-04-20", fatura_propria, 1)
    if terceiros is not None:
        compra(conn, uid, cartao_id, "2026-04-21", terceiros, 1, pessoa=nova_pessoa(conn, uid, "b"))
    return uid, corrente, cartao_id


def _confere(s: dict[str, Any], esperado: dict[str, Any]) -> None:
    for campo in ("disponivel", "compromissos", "sobra"):
        assert s[campo] == dec(esperado[campo]), campo
    assert s["alerta"] is esperado["alerta"]


def test_f_r2_01(conn: psycopg.Connection) -> None:
    """AC-1: sobra positiva = 8000.00 - 6700.00 = 1300.00; sem vencidas."""
    f = fixture("F-R2-01")
    uid, _, _ = _basico(conn, f["entrada"], f["entrada"]["fatura_propria_no_horizonte"])
    s = situacao(conn, uid, f["entrada"]["hoje"])
    _confere(s, f["esperado"])
    assert s["horizonte_dias"] == f["entrada"]["horizonte_dias"]
    assert s["data_fim"] == date(2026, 5, 20)
    assert s["vencidas"] == 0
    assert s["pendencias_vencimento"] == 0
    assert s["fixos_pendentes"] == dec("2500.00")
    assert s["faturas_proprias"] == dec("4200.00")


def test_f_r2_02(conn: psycopg.Connection) -> None:
    """AC-1: sobra negativa = 8000.00 - 8500.00 = -500.00 dispara o alerta."""
    f = fixture("F-R2-02")
    uid, _, _ = _basico(conn, f["entrada"], f["entrada"]["fatura_propria_no_horizonte"])
    _confere(situacao(conn, uid, HOJE), f["esperado"])


def test_f_r2_03(conn: psycopg.Connection) -> None:
    """AC-2 / INV-18: terceiros, a receber e crédito do vale ficam fora; só a fatura própria."""
    f = fixture("F-R2-03")
    e, esperado = f["entrada"], f["esperado"]
    total, terceiros = dec(e["fatura_total_no_horizonte"]), dec(e["fatura_terceiros"])
    assert total - terceiros == dec(esperado["fatura_propria"])  # 5000.00 - 800.00
    uid, corrente, cartao_id = _basico(
        conn, e, esperado["fatura_propria"], terceiros=e["fatura_terceiros"]
    )
    vale = conta(conn, uid, "vale", "beneficio")
    lancar(conn, uid, "receita", "2026-05-02", vale, e["credito_vale_no_mes"])
    assert resumo_fatura(conn, uid, cartao_id, "2026-05") == (
        total,
        dec(esperado["fatura_propria"]),
        terceiros,
    )  # "total 5000.00 = propria 4200.00 + terceiros 800.00"
    s = situacao(conn, uid, HOJE)
    assert s["faturas_proprias"] == dec(esperado["fatura_propria"])
    assert s["sobra"] == dec(esperado["sobra"])
    assert s["saldos_correntes"] == dec(e["saldos_correntes"])  # o crédito do vale não soma
    [fatura] = [i for i in itens(conn, uid, HOJE) if i["grupo"] == "fatura"]
    assert fatura["bruto"] == dec(esperado["fatura_propria"])  # a de terceiros não aparece


def _nomes(conn: psycopg.Connection, uid: int, linhas: list[dict[str, Any]]) -> list[str]:
    por_id = {r["recorrente_id"]: r["nome"] for r in ocorrencias(conn, uid, "2026-05")}
    return [por_id[linha["recorrente_id"]] for linha in linhas]


def test_f_r2_04(conn: psycopg.Connection) -> None:
    """AC-1 / AC-4: vinculada sai; vencida não vinculada vai à lista separada e fica fora."""
    f = fixture("F-R2-04")
    uid, corrente = usuario_com_corrente(conn, "1000.00")
    ids = {}
    for o in f["entrada"]["ocorrencias"]:
        dia_mes = int(o["data"][-2:])
        ids[o["nome"]], _ = recorrente(
            conn, uid, o["nome"], "fixo", o["valor"], dia_mes, corrente, "2026-05"
        )
    pago, _, _ = lancar(conn, uid, "debito", "2026-05-08", corrente, "300.00")
    vincular(conn, uid, ids["fixo_b"], "2026-05", pago)
    hoje = f["entrada"]["hoje"]
    s = situacao(conn, uid, hoje)
    assert s["fixos_pendentes"] == dec(f["esperado"]["compromissos_fixos"])
    assert s["compromissos"] == dec("200.00")
    assert s["saldos_correntes"] == dec("700.00")  # 1000.00 - 300.00 do débito vinculado
    assert s["sobra"] == dec("500.00")
    assert s["vencidas"] == 1
    todos = itens(conn, uid, hoje)
    vencidas = [i for i in todos if i["grupo"] == "vencida"]
    assert _nomes(conn, uid, vencidas) == f["esperado"]["vencidas_nao_vinculadas"]
    assert vencidas[0]["valor"] == dec("400.00")
    assert vencidas[0]["data"] == date(2026, 5, 5)
    fixos = [i for i in todos if i["grupo"] == "fixo"]
    assert [(i["data"], i["valor"]) for i in fixos] == [(date(2026, 5, 15), dec("200.00"))]


def test_limites_do_horizonte(conn: psycopg.Connection) -> None:
    """AC-3 / F-R2-05: hoje e hoje + horizonte entram; +1 não; hoje - 1 é vencida."""
    f = fixture("F-R2-05")
    e, esperado = f["entrada"], f["esperado"]
    uid, corrente = usuario_com_corrente(conn, e["saldos_correntes"])
    for fixo in e["fixos"]:
        recorrente(
            conn,
            uid,
            fixo["nome"],
            "fixo",
            fixo["valor"],
            int(fixo["data"][-2:]),
            corrente,
            "2026-05",
        )
    for rec in e["receitas"]:
        recorrente(
            conn,
            uid,
            rec["nome"],
            "receita",
            rec["valor"],
            int(rec["data"][-2:]),
            corrente,
            "2026-05",
        )
    s = situacao(conn, uid, e["hoje"])
    assert s["data_fim"] == date(2026, 5, 20)
    for campo in ("fixos_pendentes", "receitas_pendentes", "disponivel", "compromissos", "sobra"):
        assert s[campo] == dec(esperado[campo]), campo
    assert s["alerta"] is esperado["alerta"]
    todos = itens(conn, uid, e["hoje"])
    assert [(i["grupo"], i["data"]) for i in todos if i["grupo"] != "vencida"] == [
        ("fixo", date(2026, 5, 10)),
        ("fixo", date(2026, 5, 20)),
        ("receita", date(2026, 5, 20)),
    ]
    assert (
        _nomes(conn, uid, [i for i in todos if i["grupo"] == "vencida"])
        == esperado["vencidas_nao_vinculadas"]
    )
    # um dia depois, o de 21/05 entra e o de 10/05 vira vencido
    s2 = situacao(conn, uid, "2026-05-11")
    assert s2["fixos_pendentes"] == dec("600.00")  # 200.00 + 400.00
    assert s2["vencidas"] == 2  # 09/05 e 10/05


def test_vencimento_f_r2_06(conn: psycopg.Connection) -> None:
    """AC-6: vence em M se vencimento > fechamento; senão em M+1; dia inexistente = último dia."""
    f = fixture("F-R2-06")
    uid = novo_usuario(conn)
    obtidos = []
    for n, caso in enumerate(f["entrada"]["casos"]):
        c = novo_cartao(conn, uid, caso["fechamento"], caso["vencimento"], nome=f"c{n}")
        obtidos.append(vencimento(conn, uid, c, caso["competencia"]))
    assert obtidos == [dia(t) for t in f["esperado"]["vencimentos"]]


def test_vencimento_com_vigencia_f_r2_06(conn: psycopg.Connection) -> None:
    """AC-6: vale o vencimento vigente no último dia da competência."""
    v = fixture("F-R2-06")["entrada"]["vigencias_do_vencimento"]
    uid = novo_usuario(conn)
    c = novo_cartao(conn, uid, v["fechamento"], None)
    assert vencimento(conn, uid, c, "2026-05") is None  # sem vencimento cadastrado
    for vig in v["vencimentos"]:
        definir_vencimento(conn, uid, c, vig["dia"], vig["desde"])
    obtidos = [vencimento(conn, uid, c, comp) for comp in v["competencias"]]
    assert obtidos == [dia(t) for t in fixture("F-R2-06")["esperado"]["vencimentos_com_vigencia"]]


def test_r2_que_cruza_o_mes_f_r2_06(conn: psycopg.Connection) -> None:
    """AC-6: fechamento 25 e vencimento 5; a competência 2026-04 vence em 05/05 e entra."""
    f = fixture("F-R2-06")["r2_que_cruza_o_mes"]
    uid, _ = usuario_com_corrente(conn, f["saldos_correntes"])
    c = novo_cartao(conn, uid, 25, 5)
    for x in f["compras"]:
        compra(conn, uid, c, x["data"], x["total"], x["parcelas"])
    s = situacao(conn, uid, f["hoje"])
    assert s["data_fim"] == date(2026, 5, 5)
    assert vencimento(conn, uid, c, "2026-04") == date(2026, 5, 5)
    assert vencimento(conn, uid, c, "2026-05") == date(2026, 6, 5)
    for campo, valor in f["esperado"].items():
        assert s[campo] == dec(valor), campo
    [fatura] = [i for i in itens(conn, uid, f["hoje"]) if i["grupo"] == "fatura"]
    assert (fatura["competencia"], fatura["data"]) == ("2026-04", date(2026, 5, 5))
    # um dia antes do fim do horizonte a mesma fatura vence um dia depois do limite: fora
    assert situacao(conn, uid, "2026-04-24")["faturas_proprias"] == dec("0.00")


def test_pagamento_parcial_f_r2_07(conn: psycopg.Connection) -> None:
    """AC-7 / ADR 044: o compromisso desconta o pago alocado às parcelas próprias."""
    f = fixture("F-R2-07")
    e, esperado = f["entrada"], f["esperado"]
    uid, corrente = usuario_com_corrente(conn, e["saldos_correntes"]["snapshot"]["valor"])
    c = novo_cartao(conn, uid, e["cartao"]["fechamento"], e["cartao"]["vencimento"])
    b = nova_pessoa(conn, uid, "pessoa_b")
    for x in e["compras"]:
        extra = {"pessoa": b} if x["pessoa"] == "pessoa_b" else {}
        compra(conn, uid, c, x["data"], x["total"], x["parcelas"], **extra)
    for p in e["pagamentos"]:
        lancar(conn, uid, "transferencia", p["data"], corrente, p["valor"], destino=c)
    assert resumo_fatura(conn, uid, c, "2026-05") == (
        dec(esperado["fatura_2026_05"]["total"]),
        dec(esperado["fatura_2026_05"]["propria"]),
        dec(esperado["fatura_2026_05"]["terceiros"]),
    )
    s = situacao(conn, uid, e["hoje"])
    assert s["saldos_correntes"] == dec(esperado["saldos_correntes"])
    assert s["faturas_proprias"] == dec(esperado["faturas_proprias"])
    assert s["compromissos"] == dec(esperado["compromissos"])
    assert s["sobra"] == dec(esperado["sobra"])
    [fatura] = [i for i in itens(conn, uid, e["hoje"]) if i["grupo"] == "fatura"]
    assert fatura["bruto"] == dec("1000.00")
    assert fatura["pago"] == dec(esperado["pago_alocado_proprio"])
    assert fatura["valor"] == dec("750.00")
    assert fatura["parcial"] is esperado["parcial"]
    # pagamento antecipado maior que a dívida: a fatura não gera compromisso negativo
    lancar(conn, uid, "transferencia", "2026-05-02", corrente, "2000.00", destino=c)
    s2 = situacao(conn, uid, e["hoje"])
    assert s2["faturas_proprias"] == dec("0.00")
    assert s2["saldos_correntes"] == dec("550.00")  # 2550.00 - 2000.00


def test_fatura_aberta_aparece_como_parcial_f_r2_08(conn: psycopg.Connection) -> None:
    """AC-7: hoje antes do fechamento, a fatura é parcial e já pesa na sobra."""
    f = fixture("F-R2-08")
    e, esperado = f["entrada"], f["esperado"]
    uid, _ = usuario_com_corrente(conn, e["saldos_correntes"]["snapshot"]["valor"])
    c = novo_cartao(conn, uid, e["cartao"]["fechamento"], e["cartao"]["vencimento"])
    for x in e["compras"]:
        compra(conn, uid, c, x["data"], x["total"], x["parcelas"])
    s = situacao(conn, uid, e["hoje"])
    assert s["faturas_proprias"] == dec(esperado["faturas_proprias"])
    assert s["compromissos"] == dec(esperado["compromissos"])
    assert s["sobra"] == dec(esperado["sobra"])
    [fatura] = [i for i in itens(conn, uid, e["hoje"]) if i["grupo"] == "fatura"]
    assert fatura["parcial"] is esperado["parcial"]
    assert (fatura["competencia"], fatura["data"]) == ("2026-05", date(2026, 5, 15))
    # no dia do fechamento a fatura 2026-05 já não é parcial
    [fechada] = [i for i in itens(conn, uid, "2026-05-10") if i["grupo"] == "fatura"]
    assert fechada["parcial"] is False


def test_cartao_sem_vencimento_vira_pendencia(conn: psycopg.Connection) -> None:
    """AC-7: cartão com dívida e sem vencimento não entra na sobra e é contado à parte."""
    uid, _ = usuario_com_corrente(conn, "1000.00")
    c = novo_cartao(conn, uid, 10, None)
    compra(conn, uid, c, "2026-04-20", "300.00", 1)
    antes = situacao(conn, uid, HOJE)
    assert antes["pendencias_vencimento"] == 1
    assert antes["faturas_proprias"] == dec("0.00")
    assert antes["sobra"] == dec("1000.00")
    definir_vencimento(conn, uid, c, 20, "2026-01-01")
    depois = situacao(conn, uid, HOJE)
    assert depois["pendencias_vencimento"] == 0
    assert depois["faturas_proprias"] == dec("300.00")
    assert depois["sobra"] == dec("700.00")
    # cartão sem dívida e sem vencimento não é pendência
    uid2, _ = usuario_com_corrente(conn, "0.00")
    novo_cartao(conn, uid2, 10, None)
    assert situacao(conn, uid2, HOJE)["pendencias_vencimento"] == 0


def test_disponivel_so_contas_correntes(conn: psycopg.Connection) -> None:
    """AC-8: reserva, investimento, benefício e dívida ficam fora do disponível."""
    uid, corrente = usuario_com_corrente(conn, "1000.00")
    outra = conta(conn, uid, "corrente_2")
    snapshot(conn, uid, outra, "2026-01-01", "200.00")
    for nome, tipo, valor in (
        ("reserva", "reserva", "5000.00"),
        ("invest", "investimento", "3000.00"),
        ("vale", "beneficio", "2000.00"),
    ):
        c = conta(conn, uid, nome, tipo, mae=None if tipo == "beneficio" else corrente)
        snapshot(conn, uid, c, "2026-01-01", valor)
    novo_cartao(conn, uid, 10, 20)
    s = situacao(conn, uid, HOJE)
    assert s["saldos_correntes"] == dec("1200.00")
    assert s["disponivel"] == dec("1200.00")
    # conta corrente excluída logicamente sai do disponível
    conn.execute(
        "UPDATE conta_versao SET vigente = false WHERE user_id = %s AND conta_id = %s AND vigente",
        (uid, outra),
    )
    conn.execute(
        "INSERT INTO conta_versao (user_id, conta_id, versao, vigente, excluida, nome, tipo) "
        "VALUES (%s, %s, 2, true, true, 'corrente_2', 'corrente')",
        (uid, outra),
    )
    assert situacao(conn, uid, HOJE)["saldos_correntes"] == dec("1000.00")


def test_horizonte_com_vigencia_f_r2_09(conn: psycopg.Connection) -> None:
    """AC-9: vale o horizonte de maior vigente_desde <= hoje; sem parâmetro, 10."""
    f = fixture("F-R2-09")
    e, esperado = f["entrada"], f["esperado"]
    uid, corrente = usuario_com_corrente(conn, e["saldos_correntes"])
    for fixo in e["fixos"]:
        recorrente(conn, uid, fixo["nome"], "fixo", fixo["valor"], fixo["dia"], corrente, "2026-06")
    sem = situacao(conn, uid, "2026-05-31")
    assert sem["horizonte_dias"] == esperado["sem_parametro"]["horizonte_dias"]
    for p in e["parametros"]:
        definir_horizonte(conn, uid, p["dias"], p["desde"])
    for hoje, chave in (("2026-05-31", "hoje_2026_05_31"), ("2026-06-01", "hoje_2026_06_01")):
        s = situacao(conn, uid, hoje)
        alvo = esperado[chave]
        assert s["horizonte_dias"] == alvo["horizonte_dias"]
        assert s["data_fim"] == dia(alvo["data_fim"])
        assert s["compromissos"] == dec(alvo["compromissos"])
        assert s["sobra"] == dec(alvo["sobra"])
        assert s["alerta"] is alvo["alerta"]
    # antes de qualquer vigência (hoje anterior a 2026-01-01) volta ao padrão
    assert situacao(conn, uid, "2025-12-31")["horizonte_dias"] == 10


def test_r2_parametro_validacao_e_idempotencia(conn: psycopg.Connection) -> None:
    """AC-9: 1 a 90 dias; repetir é idempotente; mesma vigência com outro valor vale o último."""
    uid, _ = usuario_com_corrente(conn)
    for dias in (0, 91, -1):
        with Recusa(conn, "AB422"):
            definir_horizonte(conn, uid, dias, "2026-01-01")
    with Recusa(conn, "AB422"):
        definir_horizonte(conn, uid, 10, "1999-12-31")
    with Recusa(conn, "AB404"):
        definir_horizonte(conn, 999999999, 10, "2026-01-01")
    primeiro = definir_horizonte(conn, uid, 90, "2026-01-01")
    assert definir_horizonte(conn, uid, 90, "2026-01-01") == primeiro
    linhas = conn.execute("SELECT count(*) FROM r2_parametro WHERE user_id = %s", (uid,)).fetchone()
    assert linhas == (1,)
    definir_horizonte(conn, uid, 1, "2026-01-01")
    assert situacao(conn, uid, "2026-02-01")["horizonte_dias"] == 1
    definir_horizonte(conn, uid, 30, "2026-06-01")  # futuro: vale só a partir da data
    assert situacao(conn, uid, "2026-05-31")["horizonte_dias"] == 1
    assert situacao(conn, uid, "2026-06-01")["horizonte_dias"] == 30


def test_vencimento_gravar_validacao_e_idempotencia(conn: psycopg.Connection) -> None:
    """AC-6: dia de 1 a 31; só em cartão; idempotente; a vigência é por cartão."""
    uid, corrente = usuario_com_corrente(conn)
    c = novo_cartao(conn, uid, 10, None)
    for dia_venc in (0, 32):
        with Recusa(conn, "AB422"):
            definir_vencimento(conn, uid, c, dia_venc, "2026-01-01")
    with Recusa(conn, "AB422"):
        definir_vencimento(conn, uid, c, 5, "1999-12-31")
    with Recusa(conn, "AB404"):
        definir_vencimento(conn, uid, corrente, 5, "2026-01-01")  # conta corrente não é cartão
    with Recusa(conn, "AB404"):
        definir_vencimento(conn, uid, 987654321, 5, "2026-01-01")
    primeiro = definir_vencimento(conn, uid, c, 20, "2026-01-01")
    assert definir_vencimento(conn, uid, c, 20, "2026-01-01") == primeiro
    definir_vencimento(conn, uid, c, 28, "2026-01-01")  # mesma vigência, outro dia: vale o último
    assert vencimento(conn, uid, c, "2026-05") == date(2026, 5, 28)
    outro = novo_cartao(conn, uid, 10, 15, nome="outro")
    assert vencimento(conn, uid, outro, "2026-05") == date(2026, 5, 15)


def test_isolamento_por_user_id(conn: psycopg.Connection) -> None:
    """AC-11 / INV-13: com o user_id de outro usuário nada do dono aparece."""
    f = fixture("F-R2-01")
    dono, _, cartao_id = _basico(conn, f["entrada"], f["entrada"]["fatura_propria_no_horizonte"])
    definir_horizonte(conn, dono, 30, "2026-01-01")
    outro, _ = usuario_com_corrente(conn, "0.00")
    s = situacao(conn, outro, HOJE)
    assert s["horizonte_dias"] == 10  # o horizonte do dono (30) não vaza
    for campo in (
        "saldos_correntes",
        "receitas_pendentes",
        "disponivel",
        "fixos_pendentes",
        "faturas_proprias",
        "compromissos",
        "sobra",
    ):
        assert s[campo] == dec("0.00"), campo
    assert s["alerta"] is False
    assert (s["vencidas"], s["pendencias_vencimento"]) == (0, 0)
    assert itens(conn, outro, HOJE) == []
    assert ocorrencias(conn, outro, "2026-05") == []
    assert vencimento(conn, outro, cartao_id, "2026-05") is None
    assert conn.execute(
        "SELECT count(*) FROM vencimento_vigente WHERE user_id = %s", (outro,)
    ).fetchone() == (0,)
    # e o dono continua vendo o dele
    assert situacao(conn, dono, HOJE)["horizonte_dias"] == 30


def test_a_data_de_hoje_e_obrigatoria(conn: psycopg.Connection) -> None:
    uid, _ = usuario_com_corrente(conn)
    for consulta in ("r2_situacao", "r2_itens"):
        with Recusa(conn, "AB422"):
            conn.execute(f"SELECT * FROM {consulta}(%s, NULL)", (uid,))  # noqa: S608


def test_vinculo_devolve_a_ocorrencia_ao_r2(conn: psycopg.Connection) -> None:
    """AC-4: vincular tira a ocorrência da sobra e desvincular a traz de volta."""
    uid, corrente = usuario_com_corrente(conn, "1000.00")
    rid, _ = recorrente(conn, uid, "internet", "fixo", "100.00", 12, corrente, "2026-05")
    assert situacao(conn, uid, HOJE)["sobra"] == dec("900.00")
    pago, _, _ = lancar(conn, uid, "debito", "2026-05-08", corrente, "100.00")
    vincular(conn, uid, rid, "2026-05", pago)
    assert situacao(conn, uid, HOJE)["fixos_pendentes"] == dec("0.00")
    desvincular(conn, uid, rid, "2026-05")
    assert situacao(conn, uid, HOJE)["fixos_pendentes"] == dec("100.00")


def _f07(conn: psycopg.Connection, data_pagamento: str) -> int:
    """Cenário de F-R2-07 com a data do pagamento escolhida."""
    e = fixture("F-R2-07")["entrada"]
    uid, corrente = usuario_com_corrente(conn, e["saldos_correntes"]["snapshot"]["valor"])
    c = novo_cartao(conn, uid, e["cartao"]["fechamento"], e["cartao"]["vencimento"])
    b = nova_pessoa(conn, uid, "pessoa_b")
    for x in e["compras"]:
        extra = {"pessoa": b} if x["pessoa"] == "pessoa_b" else {}
        compra(conn, uid, c, x["data"], x["total"], x["parcelas"], **extra)
    for p in e["pagamentos"]:
        lancar(conn, uid, "transferencia", data_pagamento, corrente, p["valor"], destino=c)
    return uid


def test_terceiro_anterior_absorve_o_pago_f_r2_12(conn: psycopg.Connection) -> None:
    """AC-7: o pago segue a ordem competência/data/parcela, sem distinguir terceiros (ADR 044)."""
    f = fixture("F-R2-12")
    e = f["entrada"]
    for caso, chave in zip(e["casos"], ("caso_1", "caso_2", "caso_3"), strict=True):
        esperado = f["esperado"][chave]
        uid, corrente = usuario_com_corrente(conn, e["saldo_inicial"])
        c = novo_cartao(conn, uid, 10, 20)
        b = nova_pessoa(conn, uid, "pessoa_b")
        for x in e["compras"]:
            extra = {"pessoa": b} if x["pessoa"] == "pessoa_b" else {}
            compra(conn, uid, c, x["data"], x["total"], 1, **extra)
        lancar(conn, uid, "transferencia", "2026-04-30", corrente, caso["pagamento"], destino=c)
        s = situacao(conn, uid, e["hoje"])
        [fatura] = [i for i in itens(conn, uid, e["hoje"]) if i["grupo"] == "fatura"]
        assert fatura["competencia"] == "2026-05"
        assert fatura["pago"] == dec(esperado["pago_alocado_proprio"]), chave
        assert s["faturas_proprias"] == dec(esperado["faturas_proprias"]), chave
        assert s["saldos_correntes"] == dec(esperado["saldos_correntes"]), chave
        assert s["sobra"] == dec(esperado["sobra"]), chave


def test_vigencia_retroativa_f_r2_13(conn: psycopg.Connection) -> None:
    """AC-6: vencimento cadastrado hoje vale para a competência passada que vence no horizonte."""
    f = fixture("F-R2-13")
    e, esperado = f["entrada"], f["esperado"]
    uid, _ = usuario_com_corrente(conn, e["saldo_inicial"])
    c = novo_cartao(conn, uid, e["cartao"]["fechamento"]["dia"], None)
    venc = e["cartao"]["vencimento"]
    definir_vencimento(conn, uid, c, venc["dia"], venc["desde"])
    for x in e["compras"]:
        compra(conn, uid, c, x["data"], x["total"], x["parcelas"])
    assert vencimento(conn, uid, c, "2026-04") == dia(esperado["vencimento_2026_04"])
    assert vencimento(conn, uid, c, "2026-05") == dia(esperado["vencimento_2026_05"])
    s = situacao(conn, uid, e["hoje"])
    assert s["faturas_proprias"] == dec(esperado["faturas_proprias"])
    assert s["sobra"] == dec(esperado["sobra"])
    assert s["pendencias_vencimento"] == esperado["pendencias_vencimento"]
    [fatura] = [i for i in itens(conn, uid, e["hoje"]) if i["grupo"] == "fatura"]
    assert (fatura["competencia"], fatura["data"]) == ("2026-04", date(2026, 5, 5))

    # só vigência futura (fechamento e vencimento): vale também para competência anterior a ela
    fut = e["cartao_so_com_vigencia_futura"]
    uid2 = novo_usuario(conn)
    linha, _ = linha_credito(conn, uid2, "linha", "1000.00")
    c2 = cartao(conn, uid2, "c2", linha, fut["fechamento"]["dia"], fut["fechamento"]["desde"])
    definir_vencimento(conn, uid2, c2, fut["vencimento"]["dia"], fut["vencimento"]["desde"])
    esp2 = esperado["cartao_so_com_vigencia_futura"]
    assert fechamento_da_fatura(conn, uid2, c2, "2026-04") == dia(esp2["fechamento_2026_04"])
    assert vencimento(conn, uid2, c2, "2026-04") == dia(esp2["vencimento_2026_04"])

    # sem nenhum vencimento: continua pendência e fora da sobra
    uid3, _ = usuario_com_corrente(conn, e["saldo_inicial"])
    c3 = novo_cartao(conn, uid3, 25, None)
    compra(conn, uid3, c3, "2026-03-30", "900.00", 1)
    s3 = situacao(conn, uid3, e["hoje"])
    assert (s3["pendencias_vencimento"], s3["faturas_proprias"]) == (1, dec("0.00"))


def test_data_futura_nao_abate_f_r2_14(conn: psycopg.Connection) -> None:
    """AC-7: pagamento com data > hoje não abate a fatura; débito vinculado futuro não tira."""
    f = fixture("F-R2-14")
    pf = f["entrada"]["pagamento_futuro"]
    uid = _f07(conn, pf["data_do_pagamento"])
    for hoje, chave in (("2026-05-10", "hoje_2026_05_10"), ("2026-05-15", "hoje_2026_05_15")):
        s = situacao(conn, uid, hoje)
        esperado = f["esperado"]["pagamento_futuro"][chave]
        for campo, valor in esperado.items():
            assert s[campo] == dec(valor), (hoje, campo)
    # a função pública do ADR 044 não mudou: ela enxerga o pagamento, com a data que for
    publico = conn.execute(
        "SELECT sum(a.alocado) FROM alocacao_pago(%s, (SELECT conta_id FROM conta_versao "
        "WHERE user_id = %s AND tipo = 'divida' AND vigente)) a",
        (uid, uid),
    ).fetchone()
    assert publico == (dec("450.00"),)

    vf = f["entrada"]["vinculo_futuro"]
    uid2, corrente = usuario_com_corrente(conn, vf["saldo_inicial"])
    r = vf["recorrente"]
    rid, _ = recorrente(
        conn, uid2, "fixo", r["tipo"], r["valor"], r["dia"], corrente, r["mes_inicio"]
    )
    t = vf["transacao"]
    tid, _, _ = lancar(conn, uid2, t["tipo"], t["data"], corrente, t["valor"])
    vincular(conn, uid2, rid, "2026-05", tid)
    for hoje, chave in (("2026-05-10", "hoje_2026_05_10"), ("2026-05-12", "hoje_2026_05_12")):
        s = situacao(conn, uid2, hoje)
        for campo, valor in f["esperado"]["vinculo_futuro"][chave].items():
            assert s[campo] == dec(valor), (hoje, campo)
    # a ocorrência continua vinculada na lista do mês (o vínculo é real); só o R2 espera a data
    [o] = ocorrencias(conn, uid2, "2026-05")
    assert o["vinculada"] is True


def test_vigencia_absurda_e_recusada(conn: psycopg.Connection) -> None:
    """Parâmetros com vigência: nada além de 5 anos no futuro (evita sombrear a configuração)."""
    uid, _ = usuario_com_corrente(conn)
    c = novo_cartao(conn, uid, 10, None)
    longe = date.today().replace(year=date.today().year + 6, day=1).isoformat()
    perto = date.today().replace(year=date.today().year + 1, day=1).isoformat()
    with Recusa(conn, "AB422"):
        definir_horizonte(conn, uid, 10, longe)
    with Recusa(conn, "AB422"):
        definir_horizonte(conn, uid, 10, "2999-12-31")
    with Recusa(conn, "AB422"):
        definir_vencimento(conn, uid, c, 5, longe)
    definir_horizonte(conn, uid, 10, perto)
    definir_vencimento(conn, uid, c, 5, perto)


def test_vencidas_ate_24_meses_f_r2_15(conn: psycopg.Connection) -> None:
    """Retroatividade das vencidas limitada a 24 meses a partir de hoje (piso inclusive)."""
    f = fixture("F-R2-15")
    hoje = f["entrada"]["hoje"]
    uid, corrente = usuario_com_corrente(conn)
    ids = {}
    for r in f["entrada"]["recorrentes"]:
        ids[r["dia"]], _ = recorrente(
            conn, uid, f"dia{r['dia']}", "fixo", "10.00", r["dia"], corrente, "2020-01"
        )
    vencidas = [i for i in itens(conn, uid, hoje) if i["grupo"] == "vencida"]
    for r in f["entrada"]["recorrentes"]:
        esperado = f["esperado"][f"dia_{r['dia']}"]
        datas = sorted(i["data"] for i in vencidas if i["recorrente_id"] == ids[r["dia"]])
        assert len(datas) == esperado["vencidas"], r
        assert (datas[0], datas[-1]) == (dia(esperado["primeira"]), dia(esperado["ultima"])), r
    assert situacao(conn, uid, hoje)["vencidas"] == len(vencidas)
    assert situacao(conn, uid, hoje)["compromissos"] == dec(
        "20.00"
    )  # dias 10 e 15 de maio, no horizonte
