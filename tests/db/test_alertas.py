"""SPEC-011 / ADR 049: alertas R1, R2 e R4 derivados na hora (função `alertas`).

Esperados de F-ALERTA-01 a F-ALERTA-04 (fixtures/numericos.yaml), calculados à mão.
"""

from __future__ import annotations

from typing import Any

import psycopg
import pytest

from tests.db.util_alertas import (
    HOJE,
    alertas,
    chave,
    conta_com_snapshots,
    de,
    r2_base,
    reserva_com_saldo,
)
from tests.db.util_lancamento import cartao, compra, conta, lancar, linha_credito
from tests.db.util_r2 import recorrente, usuario_com_corrente
from tests.db.util_reserva import nova_reserva, parametro
from tests.db.util_saldo import dec, fixture, novo_usuario, snapshot

pytestmark = pytest.mark.banco


def _esperado(alerta: dict[str, Any]) -> tuple[str, str, str, str]:
    return alerta["codigo"], alerta["tipo"], alerta["severidade"], alerta["detalhe"]


def test_r1_severidade_por_nivel_f_alerta_01(conn: psycopg.Connection) -> None:
    """AC-1: crítica = alerta alta; atenção = aviso media; saudável = nada."""
    f = fixture("F-ALERTA-01")
    for caso in f["casos"]:
        uid = reserva_com_saldo(conn, caso["saldo"])
        lista = alertas(conn, uid, f["entrada"]["hoje"])
        esperado = caso["alerta"]
        if esperado is None:
            assert lista == [], caso["saldo"]
            continue
        assert len(lista) == 1, caso["saldo"]
        a = lista[0]
        assert _esperado(esperado) == chave(a), caso["saldo"]
        assert a["nivel"] == esperado["nivel"]
        assert a["falta"] == dec(esperado["falta"])
        assert a["saldo_liquido"] == dec(caso["saldo"])
        assert a["meta"] == dec("12000.00")
        assert a["sobra"] is None and a["conta_id"] is None  # só os campos do R1


def test_sem_conta_de_reserva_com_gasto_configurado_e_r1_critico_f_alerta_05(
    conn: psycopg.Connection,
) -> None:
    """AC-1: sem conta de reserva, mas com gasto essencial, a meta existe e o saldo é zero."""
    f = fixture("F-ALERTA-05")
    p = f["entrada"]["parametro"]
    uid = novo_usuario(conn)
    parametro(conn, uid, desde=p["desde"], meses=p["meses"], gasto=p["gasto_essencial"])
    lista = alertas(conn, uid, f["entrada"]["hoje"])
    e = f["esperado"]["alerta"]
    assert [chave(a) for a in lista] == [_esperado(e)]
    a = lista[0]
    assert a["nivel"] == e["nivel"]
    assert a["saldo_liquido"] == dec(e["saldo_liquido"])
    assert a["meta"] == dec(e["meta"])
    assert a["falta"] == dec(e["falta"])
    assert a["cobertura_meses"] == dec(e["cobertura_meses"])


def test_r4_dois_snapshots_no_mesmo_dia_valem_o_ultimo(conn: psycopg.Connection) -> None:
    """Desempate do R4: `snapshot_vigente` dá uma linha por (conta, data); vale o último gravado
    (900.00 deriva 1000.00 - 100.00 = 900.00, sem divergência; o primeiro, 950.00, divergiria)."""
    uid = novo_usuario(conn)
    c = conta_com_snapshots(
        conn,
        uid,
        "conta",
        [
            {"data": "2026-01-10", "valor": "1000.00"},
            {"data": "2026-01-14", "valor": "950.00"},
            {"data": "2026-01-14", "valor": "900.00"},
        ],
        [{"data": "2026-01-11", "valor": "-100.00"}],
    )
    assert c and de(alertas(conn, uid), "R4") == []


def test_config_pendente_nao_e_r1_f_alerta_01(conn: psycopg.Connection) -> None:
    """AC-5: gasto essencial ausente ou zero vira só o item de configuração."""
    f = fixture("F-ALERTA-01")
    esperado = f["config_pendente"]["esperado"]
    saldo = f["config_pendente"]["saldo"]
    sem_parametro = reserva_com_saldo(conn, saldo, gasto=None)
    zero = reserva_com_saldo(conn, saldo, gasto="0.00")
    for uid in (sem_parametro, zero):
        lista = alertas(conn, uid, f["entrada"]["hoje"])
        assert [chave(a) for a in lista] == [
            (esperado["codigo"], esperado["tipo"], esperado["severidade"], esperado["detalhe"])
        ]
        assert lista[0]["nivel"] is None and lista[0]["meta"] is None
        assert all(a["codigo"] != "R1" for a in lista)


def test_r2_sobra_estrita_f_alerta_02(conn: psycopg.Connection) -> None:
    """AC-2 e AC-4: só sobra < 0 alerta; zero e positiva não."""
    f = fixture("F-ALERTA-02")
    for caso in f["casos"]:
        if caso.get("cartao_sem_vencimento"):
            continue
        uid = r2_base(conn, caso["fixo"])
        lista = de(alertas(conn, uid, f["entrada"]["hoje"]), "R2")
        esperado = caso["alerta"]
        if esperado is None:
            assert lista == [], caso["fixo"]
            continue
        assert [_esperado(esperado)] == [chave(a) for a in lista], caso["fixo"]
        a = lista[0]
        assert a["sobra"] == dec(caso["sobra"])
        assert a["disponivel"] == dec("8000.00")
        assert a["sobra_nao_confiavel"] is esperado["sobra_nao_confiavel"]
        assert a["horizonte_dias"] == f["entrada"]["horizonte_dias"]


def test_r2_sobra_nao_confiavel_f_alerta_02(conn: psycopg.Connection) -> None:
    """AC-6: cartão com dívida sem vencimento marca a sobra, positiva ou negativa."""
    f = fixture("F-ALERTA-02")
    casos = [c for c in f["casos"] if c.get("cartao_sem_vencimento")]
    assert len(casos) == 2
    for caso in casos:
        uid = r2_base(conn, caso["fixo"], cartao_sem_vencimento=True)
        lista = de(alertas(conn, uid, f["entrada"]["hoje"]), "R2")
        assert [_esperado(caso["alerta"])] == [chave(a) for a in lista], caso["fixo"]
        a = lista[0]
        assert a["sobra"] == dec(caso["sobra"])
        assert a["pendencias_vencimento"] == caso["pendencias_vencimento"]
        assert a["sobra_nao_confiavel"] is True


def test_r2_vencidas_sao_aviso_a_parte_f_alerta_02(conn: psycopg.Connection) -> None:
    """AC-4: a vencida sem vínculo sai da sobra e vira aviso baixa com a quantidade."""
    f = fixture("F-ALERTA-02")["vencida"]
    uid, corrente = usuario_com_corrente(conn, "5000.00")
    recorrente(conn, uid, "salario", "receita", "3000.00", 12, corrente, "2026-05")
    recorrente(
        conn,
        uid,
        "vencido",
        "fixo",
        f["fixo"]["valor"],
        f["fixo"]["dia"],
        corrente,
        f["fixo"]["inicio"],
    )
    lista = de(alertas(conn, uid), "R2")
    assert [_esperado(f["esperado"]["alerta"])] == [chave(a) for a in lista]
    assert lista[0]["vencidas"] == f["esperado"]["vencidas"]
    assert lista[0]["sobra"] == dec(f["esperado"]["sobra"])
    assert lista[0]["sobra_nao_confiavel"] is False


def test_r4_por_conta_f_alerta_03(conn: psycopg.Connection) -> None:
    """AC-3: uma linha por conta com o snapshot divergente mais recente e a quantidade."""
    f = fixture("F-ALERTA-03")
    uid = novo_usuario(conn)
    por_conta: dict[int, dict[str, Any]] = {}
    for caso in f["casos"]:
        if caso["nome"] == "cartao":
            continue
        c = conta_com_snapshots(conn, uid, caso["nome"], caso["snapshots"], caso.get("transacoes"))
        por_conta[c] = caso
    lista = de(alertas(conn, uid), "R4")
    assert {a["conta_id"] for a in lista} == {c for c, k in por_conta.items() if k["esperado"]}
    assert len(lista) == 2
    for a in lista:
        e = por_conta[a["conta_id"]]["esperado"]
        assert ("R4", "aviso", "media", "divergencia_saldo") == chave(a)
        assert a["data_snapshot"].isoformat() == e["data_snapshot"]
        assert a["valor_snapshot"] == dec(e["valor_snapshot"])
        assert a["saldo_derivado"] == dec(e["saldo_derivado"])
        assert a["divergencia"] == dec(e["divergencia"])
        assert a["quantidade"] == e["quantidade"]
        assert a["nivel"] is None and a["sobra"] is None  # só os campos do R4


def test_r4_de_cartao_e_a_divergencia_da_conta_de_divida_f_alerta_03(
    conn: psycopg.Connection,
) -> None:
    """AC-3: na v1 o R4 de cartão é a divergência da conta de dívida."""
    caso = next(c for c in fixture("F-ALERTA-03")["casos"] if c["nome"] == "cartao")
    uid = novo_usuario(conn)
    linha, _ = linha_credito(conn, uid, "linha", "50000.00")
    cartao_id = cartao(conn, uid, "cartao", linha, 10)
    snapshot(conn, uid, cartao_id, caso["snapshots"][0]["data"], caso["snapshots"][0]["valor"])
    compra(conn, uid, cartao_id, caso["compra"]["data"], caso["compra"]["total"], 1)
    snapshot(conn, uid, cartao_id, caso["snapshots"][1]["data"], caso["snapshots"][1]["valor"])
    r4 = [a for a in alertas(conn, uid) if a["codigo"] == "R4"]
    assert len(r4) == 1
    e = caso["esperado"]
    assert r4[0]["conta_id"] == cartao_id
    assert r4[0]["saldo_derivado"] == dec(e["saldo_derivado"])
    assert r4[0]["valor_snapshot"] == dec(e["valor_snapshot"])
    assert r4[0]["divergencia"] == dec(e["divergencia"])


def test_r4_ignora_conta_excluida(conn: psycopg.Connection) -> None:
    caso = fixture("F-ALERTA-03")["casos"][0]
    uid = novo_usuario(conn)
    c = conta_com_snapshots(conn, uid, "conta", caso["snapshots"], caso["transacoes"])
    assert len(de(alertas(conn, uid), "R4")) == 1
    conn.execute(
        "UPDATE conta_versao SET excluida = true WHERE user_id = %s AND conta_id = %s", (uid, c)
    )
    assert de(alertas(conn, uid), "R4") == []


def test_combinacao_ordenada_por_severidade_f_alerta_04(conn: psycopg.Connection) -> None:
    """AC-7: vários alertas juntos saem ordenados: alta, media (R1 antes de R4), baixa."""
    f = fixture("F-ALERTA-04")
    uid = novo_usuario(conn)
    nova_reserva(conn, uid, "caixinha", {"data": "2026-01-01", "valor": "8000.00"})
    parametro(conn, uid, desde="2026-01-01", meses=3, gasto="4000.00")
    corrente = conn.execute(
        "SELECT conta_id FROM conta_versao WHERE user_id = %s AND nome = 'corrente_caixinha'",
        (uid,),
    ).fetchone()
    assert corrente is not None
    recorrente(conn, uid, "fixo_futuro", "fixo", "100.00", 15, corrente[0], "2026-05")
    recorrente(conn, uid, "fixo_vencido", "fixo", "50.00", 5, corrente[0], "2026-05")
    conta_com_snapshots(
        conn,
        uid,
        "aplicacao",
        [{"data": "2026-01-10", "valor": "1000.00"}, {"data": "2026-01-14", "valor": "1000.00"}],
        [{"data": "2026-01-11", "valor": "-50.00"}],
    )
    lista = alertas(conn, uid)
    esperado = f["esperado"]["ordem"]
    assert [chave(a) for a in lista] == [_esperado(e) for e in esperado]
    assert lista[0]["sobra"] == dec(esperado[0]["sobra"])
    assert lista[1]["nivel"] == esperado[1]["nivel"]
    assert lista[1]["falta"] == dec(esperado[1]["falta"])
    assert lista[2]["divergencia"] == dec(esperado[2]["divergencia"])
    assert lista[3]["vencidas"] == esperado[3]["vencidas"]


def test_usuario_novo_so_tem_a_configuracao_da_reserva(conn: psycopg.Connection) -> None:
    esperado = fixture("F-ALERTA-04")["sem_alertas"]["esperado"]
    lista = alertas(conn, novo_usuario(conn))
    assert [(a["codigo"], a["tipo"], a["severidade"]) for a in lista] == [
        (e["codigo"], e["tipo"], e["severidade"]) for e in esperado
    ]


def test_derivado_na_hora_sem_estado(conn: psycopg.Connection) -> None:
    """AC-8: a condição acabou, o alerta some; nada é gravado e a função só lê."""
    uid = reserva_com_saldo(conn, "3000.00")
    antes = alertas(conn, uid, "2026-04-01")
    assert [chave(a) for a in antes] == [("R1", "alerta", "alta", "reserva_critica")]
    assert alertas(conn, uid, "2026-04-01") == antes  # repetir não muda nada
    # a reserva rende 9000.00: na próxima consulta o mesmo usuário não tem alerta
    conta_reserva = conn.execute(
        "SELECT conta_id FROM conta_versao WHERE user_id = %s AND tipo = 'reserva'", (uid,)
    ).fetchone()
    assert conta_reserva is not None
    lancar(conn, uid, "rendimento", "2026-03-01", conta_reserva[0], bruto="9000.00", imposto="0.00")
    assert alertas(conn, uid, "2026-04-01") == []
    # sem estado: a função é STABLE e INVOKER, e nenhuma tabela de alerta existe
    prop = conn.execute(
        "SELECT provolatile, prosecdef FROM pg_proc "
        "WHERE oid = 'alertas(bigint, date)'::regprocedure"
    ).fetchone()
    assert prop == ("s", False)
    tabelas = conn.execute(
        "SELECT relname FROM pg_class WHERE relkind IN ('r', 'p') AND relname LIKE '%%alerta%%'"
    ).fetchall()
    assert tabelas == []


def test_isolamento_por_user_id(conn: psycopg.Connection) -> None:
    """AC-9 / INV-13: o alerta de um usuário não aparece na consulta de outro."""
    dono = reserva_com_saldo(conn, "3000.00")
    conta_com_snapshots(
        conn,
        dono,
        "aplicacao",
        [{"data": "2026-01-10", "valor": "1000.00"}, {"data": "2026-01-14", "valor": "900.00"}],
    )
    assert {a["codigo"] for a in alertas(conn, dono)} == {"R1", "R4"}
    outro = novo_usuario(conn)
    conta(conn, outro, "so_uma")
    assert [a["codigo"] for a in alertas(conn, outro)] == ["CONFIG"]
    assert alertas(conn, outro, HOJE) != alertas(conn, dono, HOJE)


def test_hoje_e_obrigatorio(conn: psycopg.Connection) -> None:
    uid = novo_usuario(conn)
    with pytest.raises(psycopg.Error, match="a data de hoje é obrigatória"):
        conn.execute("SELECT * FROM alertas(%s, NULL)", (uid,))
