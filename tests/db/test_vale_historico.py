"""SPEC-013 / ADR 052: bolso antes de marcar o VR, vigências intercaladas, trava e cadeia longa."""

from __future__ import annotations

import time
from decimal import Decimal

import psycopg
import pytest

from tests.db.util_alertas import alertas, de
from tests.db.util_lancamento import Recusa, apagar_usuario, conta, corrida, lancar
from tests.db.util_saldo import dec, fixture, novo_usuario
from tests.db.util_vale import (
    HOJE,
    credito,
    decidir,
    gasto,
    mes_do_vale,
    novo_vale,
    parametro,
    situacao,
)

pytestmark = pytest.mark.banco


def test_f_vale_12_conta_com_historico_vira_vr(conn: psycopg.Connection) -> None:
    f = fixture("F-VALE-12")["caso_1"]
    uid = novo_usuario(conn)
    h = conta(conn, uid, "h", "beneficio")
    credito(conn, uid, h, "2025-05-05", f["credito"])
    ids = [gasto(conn, uid, h, "2025-05-10", f["despesas"][0]["valor"])]
    ids.append(gasto(conn, uid, h, "2025-05-11", f["despesas"][1]["valor"]))
    with Recusa(conn, "AB422"):  # duas despesas sem bolso: marcar é recusado
        parametro(conn, uid, h, f["base_trabalho"], "2025-05-01")
    # sem VR marcado a conta de benefício aceita o bolso; classifica cada despesa
    for (tid, ver, _), d, dia_ in zip(
        ids, f["despesas"], ("2025-05-10", "2025-05-11"), strict=True
    ):
        lancar(
            conn, uid, "debito", dia_, h, d["valor"], transacao_id=tid, versao=ver, bolso=d["bolso"]
        )
    parametro(conn, uid, h, f["base_trabalho"], "2025-05-01")
    s = situacao(conn, uid, "2025-05")
    esp = f["esperado"]
    assert (s["consumo_trabalho"], s["consumo_pessoal"]) == (
        dec(esp["consumo"]["trabalho"]), dec(esp["consumo"]["pessoal"])
    )  # fmt: skip
    assert (s["alocacao_trabalho"], s["alocacao_pessoal"]) == (
        dec(esp["alocacao"]["trabalho"]), dec(esp["alocacao"]["pessoal"])
    )  # fmt: skip
    assert (s["resta_trabalho"], s["resta_pessoal"]) == (
        dec(esp["resta"]["trabalho"]), dec(esp["resta"]["pessoal"])
    )  # fmt: skip
    assert s["sobra"] == dec(esp["sobra"])
    r5 = de(alertas(conn, uid, "2025-05-20"), "R5")
    assert [(a["detalhe"], a["resta"]) for a in r5] == [
        ("vale_trabalho_estourado", dec(esp["r5_trabalho"]))
    ]


def test_f_vale_12_vigencias_intercaladas(conn: psycopg.Connection) -> None:
    f = fixture("F-VALE-12")["caso_2"]
    uid = novo_usuario(conn)
    a = conta(conn, uid, "a", "beneficio")
    b = conta(conn, uid, "b", "beneficio")
    parametro(conn, uid, b, "200.00", "2025-03-01")  # B é o VR desde março
    fev = gasto(conn, uid, a, "2025-02-10", "30.00")  # sem VR em fevereiro: sem bolso
    gasto(conn, uid, a, "2025-06-10", f["despesa_jun"]["valor"])  # B é o VR em junho
    with Recusa(conn, "AB422"):  # recusado só por causa de fevereiro
        parametro(conn, uid, a, "200.00", "2025-02-01")
    lancar(
        conn, uid, "debito", "2025-02-10", a, f["despesa_fev"]["valor"],
        transacao_id=fev[0], versao=fev[1], bolso=f["despesa_fev"]["bolso"],
    )  # fmt: skip
    parametro(conn, uid, a, "200.00", "2025-02-01")  # a de junho (sem bolso) não conta
    s_fev, s_mar = situacao(conn, uid, "2025-02"), situacao(conn, uid, "2025-03")
    assert s_fev["conta_vr_id"] == a and s_mar["conta_vr_id"] == b
    esp = f["esperado"]["fev"]["consumo"]
    assert (s_fev["consumo_trabalho"], s_fev["consumo_pessoal"]) == (
        dec(esp["trabalho"]), dec(esp["pessoal"])
    )  # fmt: skip
    assert situacao(conn, uid, "2025-06")["consumo_trabalho"] == Decimal("0.00")


def test_bolso_em_beneficio_sem_vr_e_proibicoes(conn: psycopg.Connection) -> None:
    uid = novo_usuario(conn)
    corrente = conta(conn, uid, "corrente")
    h = conta(conn, uid, "h", "beneficio")
    outra = conta(conn, uid, "o", "beneficio")
    gasto(conn, uid, h, "2025-04-10", "10.00", "pessoal")  # benefício, nenhum VR marcado
    with Recusa(conn, "AB422"):
        gasto(conn, uid, h, "2025-04-10", "10.00", "ambos")  # valor inválido
    with Recusa(conn, "AB422"):
        gasto(conn, uid, corrente, "2025-04-10", "10.00", "pessoal")  # não é de benefício
    parametro(conn, uid, outra, "200.00", "2025-01-01")  # agora outra conta é o VR
    with Recusa(conn, "AB422"):
        gasto(conn, uid, h, "2025-04-11", "10.00", "pessoal")  # o VA continua sem bolsos
    gasto(conn, uid, h, "2025-04-11", "10.00")
    # antes da vigência do VR o bolso volta a ser aceito na conta de benefício
    gasto(conn, uid, h, "2024-12-11", "10.00", "trabalho")
    # a própria conta do VR continua exigindo bolso
    with Recusa(conn, "AB422"):
        gasto(conn, uid, outra, "2025-04-11", "10.00")


def test_conta_nula_nao_vira_mensagem_de_bolso(conn: psycopg.Connection) -> None:
    """Conta ausente é 'conta não encontrada' (AB404), não 'precisa de bolso' (e sem VR marcado)."""
    uid = novo_usuario(conn)
    with Recusa(conn, "AB404"):
        conn.execute(
            "SELECT * FROM lancamento_gravar(%s, NULL, NULL, 'debito', DATE '2025-04-10', 5.00, "
            "NULL, NULL, NULL, NULL, NULL, NULL, NULL, NULL, NULL, NULL)",
            (uid,),
        )
    with Recusa(conn, "AB422"):  # e com bolso informado a recusa é a do bolso, não um erro de SQL
        conn.execute(
            "SELECT * FROM lancamento_gravar(%s, NULL, NULL, 'debito', DATE '2025-04-10', 5.00, "
            "NULL, NULL, NULL, NULL, NULL, NULL, NULL, NULL, NULL, 'pessoal')",
            (uid,),
        )


def test_cadeia_longa_de_decisoes_sem_estourar_pilha(conn: psycopg.Connection) -> None:
    """300 meses, todos com decisão trabalho/pessoal: sem recursão, tempo razoável.

    Crédito 1000.00 por mês, sem consumo: a sobra de cada mês é a alocação inteira, então
    sobra(n) = 1000.00 + sobra(n-1) e, no mês n, sobra = 1000.00 * n (calculado à mão).
    """
    v = novo_vale(conn, desde="2000-01-01")
    meses = [f"{2001 + k // 12}-{k % 12 + 1:02d}" for k in range(300)]
    for k, mes in enumerate(meses):
        credito(conn, v.uid, v.vr, f"{mes}-05", "1000.00")
        decidir(conn, v.uid, mes, "trabalho" if k % 2 == 0 else "pessoal")
    assert meses[0] == "2001-01" and meses[-1] == "2025-12"
    inicio = time.monotonic()
    ultimo = situacao(conn, v.uid, meses[-1])
    meio = situacao(conn, v.uid, meses[1])
    assert time.monotonic() - inicio < 120
    assert ultimo["sobra"] == Decimal("300000.00")
    assert ultimo["alocacao_trabalho"] + ultimo["alocacao_pessoal"] == Decimal("300000.00")
    assert meio["sobra"] == Decimal("2000.00")
    # o mês 300 recebeu o ajuste do 299: 299 * 1000.00
    assert ultimo["ajuste_trabalho"] + ultimo["ajuste_pessoal"] == Decimal("299000.00")


def _preparar(url: str) -> tuple[int, int]:
    """Usuário com a conta de benefício `h` (sem VR marcado); devolve (uid, conta)."""
    with psycopg.connect(url) as prep:
        uid = novo_usuario(prep)
        h = conta(prep, uid, "h", "beneficio")
        prep.commit()
    return uid, h


def test_corrida_despesa_antes_da_marcacao_recusa_a_marcacao(esquema: str) -> None:
    """A despesa sem bolso (lançada antes) é vista pela marcação, que espera a trava e recusa."""
    uid, h = _preparar(esquema)
    try:
        _, marcacao = corrida(
            esquema,
            lambda a: gasto(a, uid, h, "2025-05-10", "10.00"),
            lambda b: parametro(b, uid, h, "200.00", "2025-05-01"),
        )
        assert marcacao == "AB422"
        with psycopg.connect(esquema) as ver:
            n = ver.execute("SELECT count(*) FROM vale_parametro WHERE user_id = %s", (uid,))
            assert n.fetchone() == (0,)
    finally:
        apagar_usuario(esquema, uid)


def test_corrida_marcacao_antes_da_despesa_exige_bolso(esquema: str) -> None:
    """A marcação segura a trava; a despesa sem bolso espera, vê o VR e é recusada."""
    uid, h = _preparar(esquema)
    try:
        marcacao, despesa = corrida(
            esquema,
            lambda a: parametro(a, uid, h, "200.00", "2025-05-01"),
            lambda b: gasto(b, uid, h, "2025-05-10", "10.00"),
        )
        assert isinstance(marcacao, int)
        assert despesa == "AB422"
        with psycopg.connect(esquema) as ver:
            n = ver.execute(
                "SELECT count(*) FROM transacao_vigente WHERE user_id = %s", (uid,)
            ).fetchone()
            assert n == (0,)
    finally:
        apagar_usuario(esquema, uid)


def test_mes_do_vale_e_hoje_continuam_coerentes(conn: psycopg.Connection) -> None:
    """Regressão: a cadeia iterativa mantém o resultado de F-VALE-07 em outra ordem de leitura."""
    f = fixture("F-VALE-07")
    v = novo_vale(conn, base=f["entrada"]["base_trabalho"])
    for mes, m in f["entrada"]["meses"].items():
        mes_do_vale(conn, v, mes, m["credito"], m["consumo"]["trabalho"], m["consumo"]["pessoal"])
    for mes, m in f["entrada"]["meses"].items():
        if "decisao" in m:
            decidir(conn, v.uid, mes, m["decisao"])
    for mes in reversed(list(f["esperado"])):  # do último ao primeiro
        esp = f["esperado"][mes]
        s = situacao(conn, v.uid, mes, HOJE)
        assert s["sobra"] == dec(esp["sobra"]), mes
