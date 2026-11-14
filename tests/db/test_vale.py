"""SPEC-013 / ADR 052: vale (VR) com bolsos, sobra, decisão, VA e receita total.

Os esperados vêm de `fixtures/numericos.yaml` (F-VALE-01 a F-VALE-11, calculados à mão).
"""

from __future__ import annotations

from decimal import Decimal
from typing import Any

import psycopg
import pytest

from tests.db.util_lancamento import Recusa, conta, excluir, lancar
from tests.db.util_saldo import dec, dia, fixture, novo_usuario, snapshot
from tests.db.util_vale import (
    HOJE,
    Vale,
    alocacao,
    credito,
    decidir,
    gasto,
    mes_do_vale,
    novo_vale,
    parametro,
    resta,
    saldo_derivado,
    situacao,
)

pytestmark = pytest.mark.banco


def _par(d: dict[str, str]) -> tuple[Decimal, Decimal]:
    return dec(d["trabalho"]), dec(d["pessoal"])


def _mes_com(conn: psycopg.Connection, f: str, mes: str = "2025-01") -> tuple[Vale, dict[str, Any]]:
    """Cenário de um mês a partir da entrada da fixture (crédito, base e consumo)."""
    e = fixture(f)["entrada"]
    v = novo_vale(conn, base=e["base_trabalho"])
    mes_do_vale(conn, v, mes, e["credito_mes"], e["consumo"]["trabalho"], e["consumo"]["pessoal"])
    return v, situacao(conn, v.uid, mes)


def test_f_vale_01(conn: psycopg.Connection) -> None:
    """pessoal = crédito − base; trabalho = base (crédito 1000.00, base 200.00)."""
    f = fixture("F-VALE-01")
    v = novo_vale(conn, base=f["entrada"]["base_trabalho"])
    mes_do_vale(conn, v, "2025-01", f["entrada"]["credito_mes"])
    s = situacao(conn, v.uid, "2025-01")
    assert s["estado"] == "ok"
    assert (s["inicial_trabalho"], s["inicial_pessoal"]) == _par(f["esperado"])
    assert s["inicial_trabalho"] == Decimal("200.00") and s["inicial_pessoal"] == Decimal("800.00")
    assert s["credito"] == Decimal("1000.00") and s["base_trabalho"] == Decimal("200.00")
    # sem decisão anterior, a alocação efetiva é a inicial e o resta é a própria alocação
    assert alocacao(s) == (Decimal("200.00"), Decimal("800.00"))
    assert resta(s) == (Decimal("200.00"), Decimal("800.00"))


def test_f_vale_02_sobra(conn: psycopg.Connection) -> None:
    f = fixture("F-VALE-02")
    _, s = _mes_com(conn, "F-VALE-02")
    assert resta(s) == _par(f["esperado"]["resta"])
    assert s["consumo_trabalho"] == Decimal("150.00") and s["consumo_pessoal"] == Decimal("700.00")
    assert s["sobra"] == dec(f["esperado"]["sobra"]) == Decimal("150.00")


def test_f_vale_03_estouro_nao_compensado(conn: psycopg.Connection) -> None:
    f = fixture("F-VALE-03")
    _, s = _mes_com(conn, "F-VALE-03")
    assert resta(s) == _par(f["esperado"]["resta"]) == (Decimal("-50.00"), Decimal("100.00"))
    # a sobra do pessoal (100) não é reduzida pelo estouro do trabalho (−50)
    assert s["sobra"] == dec(f["esperado"]["sobra"]) == Decimal("100.00")


def test_f_vale_04_decisao(conn: psycopg.Connection) -> None:
    """A decisão soma a sobra (150.00) na alocação do mês seguinte e não move saldo."""
    f = fixture("F-VALE-04")
    base = f["entrada"]["mes_1"]["base_trabalho"]
    v = novo_vale(conn, base=base)
    mes_do_vale(conn, v, "2025-01", "1000.00", "150.00", "700.00")  # sobra 150.00 (F-VALE-02)
    mes_do_vale(conn, v, "2025-02", f["entrada"]["mes_2"]["credito"])
    # variante sem decisão: nenhum ajuste
    sem = situacao(conn, v.uid, "2025-02")
    assert alocacao(sem) == _par(f["variante_sem_decisao"]["alocacao_mes_2"])
    antes = saldo_derivado(conn, v.uid, v.vr, HOJE)
    decidir(conn, v.uid, "2025-01", f["entrada"]["mes_1"]["decisao"])
    depois = saldo_derivado(conn, v.uid, v.vr, HOJE)
    com = situacao(conn, v.uid, "2025-02")
    assert alocacao(com) == _par(f["esperado"]["alocacao_mes_2"])
    assert com["ajuste_pessoal"] == Decimal("150.00") and com["ajuste_trabalho"] == Decimal("0.00")
    assert depois - antes == dec(f["esperado"]["variacao_saldo_pela_decisao"])


def test_f_vale_05_saldo_total(conn: psycopg.Connection) -> None:
    """Saldo do VR = snapshot 100.00 + crédito 1000.00 − consumo 850.00 = 250.00 (acumula)."""
    f = fixture("F-VALE-05")
    v = novo_vale(conn)
    snapshot(conn, v.uid, v.vr, "2025-03-31", f["entrada"]["saldo_inicial_snapshot"])
    mes_do_vale(conn, v, "2025-04", f["entrada"]["credito_mes"], "150.00", "700.00")
    credito(conn, v.uid, v.corrente, "2025-04-03", f["entrada"]["receita_caixa"])
    s = situacao(conn, v.uid, "2025-04")
    assert s["saldo_total"] == dec(f["esperado"]["saldo_derivado"]) == Decimal("250.00")
    assert s["receita_total"] == dec(f["esperado"]["receita_total"]) == Decimal("6000.00")
    assert s["receita_caixa"] == dec(f["esperado"]["tela_principal_mostra"])
    # o saldo acumula: no mês seguinte (sem lançamento) continua 250.00, não zera
    assert situacao(conn, v.uid, "2025-05")["saldo_total"] == Decimal("250.00")


def test_f_vale_06_credito_menor_e_sem_credito(conn: psycopg.Connection) -> None:
    for caso in fixture("F-VALE-06")["casos"]:
        e, esp = caso["entrada"], caso["esperado"]
        v = novo_vale(conn, base=e["base_trabalho"])
        mes_do_vale(
            conn, v, "2025-01", e["credito"], e["consumo"]["trabalho"], e["consumo"]["pessoal"]
        )
        s = situacao(conn, v.uid, "2025-01")
        assert s["estado"] == esp["estado"], caso["nome"]
        assert (s["inicial_trabalho"], s["inicial_pessoal"]) == _par(esp["alocacao_inicial"])
        assert resta(s) == _par(esp["resta"]), caso["nome"]
        assert s["sobra"] == dec(esp["sobra"]), caso["nome"]


def test_f_vale_07_encadeamento(conn: psycopg.Connection) -> None:
    f = fixture("F-VALE-07")
    v = novo_vale(conn, base=f["entrada"]["base_trabalho"])
    for mes, m in f["entrada"]["meses"].items():
        mes_do_vale(conn, v, mes, m["credito"], m["consumo"]["trabalho"], m["consumo"]["pessoal"])
    for mes, m in f["entrada"]["meses"].items():
        if "decisao" in m:
            decidir(conn, v.uid, mes, m["decisao"])
    for mes, esp in f["esperado"].items():
        s = situacao(conn, v.uid, mes)
        assert (s["ajuste_trabalho"], s["ajuste_pessoal"]) == _par(esp["ajuste"]), mes
        assert alocacao(s) == _par(esp["alocacao"]), mes
        assert resta(s) == _par(esp["resta"]), mes
        assert s["sobra"] == dec(esp["sobra"]), mes
    # o mês 3 (trabalho estourado em −10) é encerrado: sem R5 e sem compensação
    assert situacao(conn, v.uid, "2025-03")["sobra"] == Decimal("200.00")


def _cenario_f09(conn: psycopg.Connection) -> Vale:
    e = fixture("F-VALE-09")["entrada"]
    v = novo_vale(conn)
    snapshot(conn, v.uid, v.vr, "2025-03-31", e["vr"]["snapshot"])
    snapshot(conn, v.uid, v.va, "2025-03-31", e["va"]["snapshot"])
    credito(conn, v.uid, v.corrente, "2025-04-02", e["receita_caixa"])
    mes_do_vale(
        conn, v, "2025-04", e["vr"]["receita"],
        e["vr"]["consumo"]["trabalho"], e["vr"]["consumo"]["pessoal"],
    )  # fmt: skip
    credito(conn, v.uid, v.va, "2025-04-06", e["va"]["receita"])
    gasto(conn, v.uid, v.va, "2025-04-12", e["va"]["despesa"])  # VA: sem bolso
    return v


def test_f_vale_09_receita_total_com_va(conn: psycopg.Connection) -> None:
    f = fixture("F-VALE-09")
    v = _cenario_f09(conn)
    s = situacao(conn, v.uid, "2025-04", f["entrada"]["hoje"])
    esp = f["esperado"]
    assert s["receita_caixa"] == dec(esp["receita_caixa"])
    assert s["receita_beneficio"] == dec(esp["receita_beneficio"]) == Decimal("1400.00")
    assert s["receita_total"] == dec(esp["receita_total"]) == Decimal("6400.00")
    assert s["saldo_total"] == dec(esp["saldo_vr"]) == Decimal("250.00")
    assert saldo_derivado(conn, v.uid, v.va, f["entrada"]["hoje"]) == dec(esp["saldo_va"])
    gasto_real = conn.execute("SELECT gasto_real(%s, '2025-04')", (v.uid,)).fetchone()
    assert gasto_real == (dec(esp["gasto_real"]),)  # VR e VA fora do gasto real
    # a conta de caixa é a única na receita de caixa: o VA não a inflou
    assert esp["tela_principal_mostra"] == esp["receita_caixa"]


def test_beneficios_contas_lista_vr_e_va(conn: psycopg.Connection) -> None:
    f = fixture("F-VALE-09")
    v = _cenario_f09(conn)
    linhas = conn.execute(
        "SELECT conta_id, vale_refeicao, receita_mes, despesa_mes, saldo_total "
        "FROM beneficios_contas(%s, '2025-04', %s) ORDER BY conta_id",
        (v.uid, dia(f["entrada"]["hoje"])),
    ).fetchall()
    assert linhas == [
        (v.vr, True, Decimal("1000.00"), Decimal("850.00"), Decimal("250.00")),
        (v.va, False, Decimal("400.00"), Decimal("120.00"), Decimal("330.00")),
    ]


def test_va_sem_bolso_e_fora_do_gasto_real(conn: psycopg.Connection) -> None:
    v = novo_vale(conn)
    with Recusa(conn, "AB422"):
        gasto(conn, v.uid, v.va, "2025-04-12", "10.00", "pessoal")  # o VA não tem bolsos
    gasto(conn, v.uid, v.va, "2025-04-12", "10.00")
    gasto(conn, v.uid, v.vr, "2025-04-13", "20.00", "pessoal")
    assert conn.execute("SELECT gasto_real(%s, '2025-04')", (v.uid,)).fetchone() == (
        Decimal("0.00"),
    )
    gasto(conn, v.uid, v.corrente, "2025-04-14", "7.00")
    assert conn.execute("SELECT gasto_real(%s, '2025-04')", (v.uid,)).fetchone() == (
        Decimal("7.00"),
    )
    # o consumo do VR não inclui a despesa do VA
    s = situacao(conn, v.uid, "2025-04")
    assert (s["consumo_trabalho"], s["consumo_pessoal"]) == (Decimal("0.00"), Decimal("20.00"))


def test_marcacao_valida_a_conta(conn: psycopg.Connection) -> None:
    v = novo_vale(conn)
    outro = novo_vale(conn)
    with Recusa(conn, "AB422"):
        parametro(conn, v.uid, v.corrente)  # conta corrente não é de benefício
    with Recusa(conn, "AB404"):
        parametro(conn, v.uid, outro.vr)  # conta de outro usuário
    with Recusa(conn, "AB404"):
        parametro(conn, v.uid, 999999999)
    with Recusa(conn, "AB422"):
        parametro(conn, v.uid, v.va, base="200.001")
    with Recusa(conn, "AB422"):
        parametro(conn, v.uid, v.va, base="-0.01")
    with Recusa(conn, "AB422"):
        parametro(conn, v.uid, v.va, padrao="ambos")
    with Recusa(conn, "AB422"):
        parametro(conn, v.uid, v.va, desde="2025-02-15")  # vigência é o dia 1
    with Recusa(conn, "AB422"):
        parametro(conn, v.uid, v.va, desde="1999-12-01")
    with Recusa(conn, "AB404"):
        parametro(conn, 999999999, v.va)
    # idempotente: repetir o que já vale devolve o mesmo registro e não grava de novo
    primeiro = parametro(conn, v.uid, v.vr, "300.00", "2025-06-01", "pessoal")
    assert parametro(conn, v.uid, v.vr, "300.00", "2025-06-01", "pessoal") == primeiro
    linhas = conn.execute(
        "SELECT count(*) FROM vale_parametro WHERE user_id = %s AND vigente_desde = %s",
        (v.uid, dia("2025-06-01")),
    ).fetchone()
    assert linhas == (1,)
    # mudar o que vale para a mesma vigência vale o último gravado, sem apagar o anterior
    parametro(conn, v.uid, v.vr, "250.00", "2025-06-01", "pessoal")
    vigente = conn.execute(
        "SELECT base_trabalho FROM vale_parametro_vigente WHERE user_id = %s "
        "AND vigente_desde = %s",
        (v.uid, dia("2025-06-01")),
    ).fetchone()
    assert vigente == (Decimal("250.00"),)
    total = conn.execute("SELECT count(*) FROM vale_parametro WHERE user_id = %s", (v.uid,))
    assert total.fetchone() == (3,)  # o inicial de novo_vale e as duas desta vigência


def test_marcacao_com_vigencia_por_mes(conn: psycopg.Connection) -> None:
    v = novo_vale(conn, desde="2025-01-01")  # VR = v.vr desde 2025-01
    parametro(conn, v.uid, v.va, "200.00", "2025-03-01")  # a partir de março o VR é a outra
    assert situacao(conn, v.uid, "2024-12")["estado"] == "sem_conta"
    assert situacao(conn, v.uid, "2025-02")["conta_vr_id"] == v.vr
    assert situacao(conn, v.uid, "2025-03")["conta_vr_id"] == v.va
    assert situacao(conn, v.uid, "2025-09")["conta_vr_id"] == v.va
    # a conta que exige bolso numa data é a vigente nela
    with Recusa(conn, "AB422"):
        gasto(conn, v.uid, v.vr, "2025-02-10", "10.00")  # em fevereiro v.vr é o VR
    gasto(conn, v.uid, v.vr, "2025-02-10", "10.00", "trabalho")
    gasto(conn, v.uid, v.vr, "2025-03-10", "10.00")  # em março deixou de ser
    with Recusa(conn, "AB422"):
        gasto(conn, v.uid, v.va, "2025-03-10", "10.00")  # agora v.va exige bolso
    gasto(conn, v.uid, v.va, "2025-02-10", "10.00")  # em fevereiro era só o VA
    # sem parâmetro anterior à data, ninguém exige bolso
    gasto(conn, v.uid, v.vr, "2024-12-10", "10.00")


def test_marcacao_recusa_despesa_sem_bolso(conn: psycopg.Connection) -> None:
    v = novo_vale(conn, desde="2025-01-01")
    gasto(conn, v.uid, v.va, "2025-04-12", "10.00")  # VA: sem bolso, permitido
    with Recusa(conn, "AB422"):
        parametro(conn, v.uid, v.va, desde="2025-03-01")  # a despesa de abril ficaria sem bolso
    parametro(conn, v.uid, v.va, desde="2025-05-01")  # depois da despesa: pode


def test_base_com_vigencia(conn: psycopg.Connection) -> None:
    v = novo_vale(conn, base="200.00", desde="2025-01-01")
    parametro(conn, v.uid, v.vr, "300.00", "2025-03-01")
    for mes in ("2025-02", "2025-03"):
        mes_do_vale(conn, v, mes, "1000.00")
    fev, mar = situacao(conn, v.uid, "2025-02"), situacao(conn, v.uid, "2025-03")
    assert (fev["inicial_trabalho"], fev["inicial_pessoal"]) == (
        Decimal("200.00"),
        Decimal("800.00"),
    )
    assert (mar["inicial_trabalho"], mar["inicial_pessoal"]) == (
        Decimal("300.00"),
        Decimal("700.00"),
    )
    assert (fev["base_trabalho"], mar["base_trabalho"]) == (Decimal("200.00"), Decimal("300.00"))
    # a base alterada não reescreve os meses anteriores
    assert situacao(conn, v.uid, "2025-02") == fev


def test_decisao_so_em_mes_encerrado(conn: psycopg.Connection) -> None:
    v = novo_vale(conn, desde="2020-01-01")
    atual = conn.execute(
        "SELECT to_char((now() AT TIME ZONE 'America/Sao_Paulo')::date, 'YYYY-MM'),"
        "       to_char((now() AT TIME ZONE 'America/Sao_Paulo')::date + interval '1 month',"
        "               'YYYY-MM'),"
        "       to_char((now() AT TIME ZONE 'America/Sao_Paulo')::date - interval '1 month',"
        "               'YYYY-MM')"
    ).fetchone()
    assert atual is not None
    corrente, futuro, anterior = atual
    with Recusa(conn, "AB422"):
        decidir(conn, v.uid, corrente, "pessoal")  # o mês civil atual não está encerrado
    with Recusa(conn, "AB422"):
        decidir(conn, v.uid, futuro, "pessoal")
    with Recusa(conn, "AB422"):
        decidir(conn, v.uid, "2019-12", "pessoal")  # sem conta de vale configurada no mês
    with Recusa(conn, "AB422"):
        decidir(conn, v.uid, "2025-13", "pessoal")  # mês fora do formato
    assert decidir(conn, v.uid, anterior, "pessoal") == 1
    # a tela marca o mês como encerrado só depois que o mês civil acaba
    assert situacao(conn, v.uid, "2025-05", "2025-05-20")["mes_encerrado"] is False
    assert situacao(conn, v.uid, "2025-05", "2025-06-01")["mes_encerrado"] is True
    assert situacao(conn, v.uid, "2025-05", "2025-05-31")["mes_encerrado"] is False


def test_decisao_destino_invalido_e_idempotente(conn: psycopg.Connection) -> None:
    v = novo_vale(conn)
    with Recusa(conn, "AB422"):
        decidir(conn, v.uid, "2025-01", "ambos")
    with Recusa(conn, "AB404"):
        decidir(conn, 999999999, "2025-01", "pessoal")
    assert decidir(conn, v.uid, "2025-01", "pessoal") == 1
    assert decidir(conn, v.uid, "2025-01", "pessoal") == 1  # repetir o vigente não cria versão
    assert decidir(conn, v.uid, "2025-01", "trabalho") == 2
    assert decidir(conn, v.uid, "2025-01", "pessoal") == 3  # voltar ao primeiro é nova versão
    linhas = conn.execute(
        "SELECT versao, destino FROM vale_decisao WHERE user_id = %s ORDER BY versao", (v.uid,)
    ).fetchall()
    assert linhas == [(1, "pessoal"), (2, "trabalho"), (3, "pessoal")]
    s = situacao(conn, v.uid, "2025-01")
    assert (s["decisao_destino"], s["decisao_versao"]) == ("pessoal", 3)


def test_f_vale_10_decisao_substituida(conn: psycopg.Connection) -> None:
    f = fixture("F-VALE-10")
    e = f["entrada"]
    v = novo_vale(conn, base=e["base_trabalho"])
    m1 = e["mes_1"]
    mes_do_vale(
        conn, v, "2025-01", m1["credito"], m1["consumo"]["trabalho"], m1["consumo"]["pessoal"]
    )
    mes_do_vale(conn, v, "2025-02", e["mes_2"]["credito"])
    assert situacao(conn, v.uid, "2025-01")["sobra"] == dec(f["esperado"]["sobra_mes_1"])
    saldo_antes = saldo_derivado(conn, v.uid, v.vr, HOJE)
    # sem decisão, sem ajuste: o destino padrão do parâmetro só pré-seleciona
    assert alocacao(situacao(conn, v.uid, "2025-02")) == (Decimal("200.00"), Decimal("800.00"))
    for destino, esperado in zip(
        e["decisoes_sobre_mes_1"], f["esperado"]["alocacao_mes_2"], strict=True
    ):
        decidir(conn, v.uid, "2025-01", destino)
        assert alocacao(situacao(conn, v.uid, "2025-02")) == _par(esperado), destino
        assert saldo_derivado(conn, v.uid, v.vr, HOJE) - saldo_antes == dec(
            f["esperado"]["variacao_saldo_por_decisao"]
        )
    versoes = conn.execute(
        "SELECT count(*) FROM vale_decisao WHERE user_id = %s", (v.uid,)
    ).fetchone()
    assert versoes == (f["esperado"]["versoes"],)
    final = situacao(conn, v.uid, "2025-01")
    assert (final["decisao_destino"], final["decisao_versao"]) == ("nenhum", 3)
    # a decisão não grava transação nem snapshot
    nada = conn.execute(
        "SELECT (SELECT count(*) FROM transacao_versao WHERE user_id = %s),"
        "       (SELECT count(*) FROM snapshot_saldo WHERE user_id = %s)",
        (v.uid, v.uid),
    ).fetchone()
    assert nada == (4, 0)  # crédito e 2 despesas de janeiro, crédito de fevereiro


def test_destino_padrao_so_pre_seleciona(conn: psycopg.Connection) -> None:
    v = novo_vale(conn)
    parametro(conn, v.uid, v.vr, "200.00", "2025-01-01", "trabalho")
    mes_do_vale(conn, v, "2025-01", "1000.00", "150.00", "700.00")
    mes_do_vale(conn, v, "2025-02", "1000.00")
    s = situacao(conn, v.uid, "2025-01")
    assert s["destino_padrao"] == "trabalho" and s["decisao_destino"] is None
    assert alocacao(situacao(conn, v.uid, "2025-02")) == (Decimal("200.00"), Decimal("800.00"))


def test_bolso_obrigatorio_no_vr(conn: psycopg.Connection) -> None:
    v = novo_vale(conn)
    with Recusa(conn, "AB422"):
        gasto(conn, v.uid, v.vr, "2025-04-10", "10.00")  # despesa no VR sem bolso
    with Recusa(conn, "AB422"):
        gasto(conn, v.uid, v.vr, "2025-04-10", "10.00", "ambos")
    with Recusa(conn, "AB422"):
        gasto(conn, v.uid, v.corrente, "2025-04-10", "10.00", "pessoal")  # fora do VR
    with Recusa(conn, "AB422"):
        lancar(conn, v.uid, "receita", "2025-04-05", v.vr, "10.00", bolso="trabalho")
    assert gasto(conn, v.uid, v.vr, "2025-04-10", "10.00", "pessoal")[2] is True
    nada = conn.execute(
        "SELECT count(*) FROM transacao_vigente WHERE user_id = %s", (v.uid,)
    ).fetchone()
    assert nada == (1,)  # as recusas não deixaram lançamento
    # quem chamava com 15 argumentos continua funcionando (sem bolso, fora do VR)
    linha = conn.execute(
        "SELECT criado FROM lancamento_gravar(%s, NULL, NULL, 'debito', DATE '2025-04-11', "
        "5.00, %s, NULL, NULL, NULL, NULL, NULL, NULL, NULL, NULL)",
        (v.uid, v.corrente),
    ).fetchone()
    assert linha == (True,)


def test_edicao_e_exclusao_acompanham_o_bolso(conn: psycopg.Connection) -> None:
    v = novo_vale(conn)
    credito(conn, v.uid, v.vr, "2025-04-05", "1000.00")
    tid, ver, _ = gasto(conn, v.uid, v.vr, "2025-04-10", "100.00", "trabalho")
    s = situacao(conn, v.uid, "2025-04")
    assert (s["consumo_trabalho"], s["consumo_pessoal"]) == (Decimal("100.00"), Decimal("0.00"))
    with Recusa(conn, "AB422"):  # a edição exige o bolso de novo
        lancar(conn, v.uid, "debito", "2025-04-10", v.vr, "60.00", transacao_id=tid, versao=ver)
    _, ver2, _ = lancar(
        conn, v.uid, "debito", "2025-04-10", v.vr, "60.00",
        transacao_id=tid, versao=ver, bolso="pessoal",
    )  # fmt: skip
    s = situacao(conn, v.uid, "2025-04")
    assert (s["consumo_trabalho"], s["consumo_pessoal"]) == (Decimal("0.00"), Decimal("60.00"))
    # a versão antiga continua guardada com o bolso dela (histórico), mas não conta
    bolsos = conn.execute(
        "SELECT versao, bolso FROM vale_bolso WHERE user_id = %s AND transacao_id = %s "
        "ORDER BY versao",
        (v.uid, tid),
    ).fetchall()
    assert bolsos == [(ver, "trabalho"), (ver2, "pessoal")]
    # mover a despesa para a corrente: sem bolso, e sai do consumo do VR
    _, ver3, _ = lancar(
        conn, v.uid, "debito", "2025-04-10", v.corrente, "60.00", transacao_id=tid, versao=ver2
    )
    assert situacao(conn, v.uid, "2025-04")["consumo_pessoal"] == Decimal("0.00")
    # volta ao VR e exclui: a exclusão lógica tira o consumo
    _, ver4, _ = lancar(
        conn, v.uid, "debito", "2025-04-10", v.vr, "60.00",
        transacao_id=tid, versao=ver3, bolso="trabalho",
    )  # fmt: skip
    assert situacao(conn, v.uid, "2025-04")["consumo_trabalho"] == Decimal("60.00")
    excluir(conn, v.uid, tid, ver4)
    s = situacao(conn, v.uid, "2025-04")
    assert (s["consumo_trabalho"], s["consumo_pessoal"]) == (Decimal("0.00"), Decimal("0.00"))
    assert s["sobra"] == Decimal("1000.00")


def test_isolamento_por_user_id(conn: psycopg.Connection) -> None:
    a = novo_vale(conn)
    mes_do_vale(conn, a, "2025-01", "1000.00", "150.00", "700.00")
    decidir(conn, a.uid, "2025-01", "pessoal")
    mes_do_vale(conn, a, "2025-02", "1000.00")
    b = novo_usuario(conn)  # outro usuário, sem vale
    s = situacao(conn, b, "2025-01")
    assert s["estado"] == "sem_conta" and s["conta_vr_id"] is None
    assert s["credito"] == Decimal("0.00") and s["sobra"] == Decimal("0.00")
    assert s["decisao_destino"] is None and s["saldo_total"] is None
    assert alocacao(situacao(conn, b, "2025-02")) == (Decimal("0.00"), Decimal("0.00"))
    assert conn.execute(
        "SELECT count(*) FROM beneficios_contas(%s, '2025-01', %s)", (b, dia(HOJE))
    ).fetchone() == (0,)
    # não pode decidir (sem VR próprio) nem marcar a conta do outro como VR
    with Recusa(conn, "AB422"):
        decidir(conn, b, "2025-01", "pessoal")
    with Recusa(conn, "AB404"):
        parametro(conn, b, a.vr)
    # e o outro usuário não vê nada do primeiro, nem a decisão de A afeta B
    assert conn.execute(
        "SELECT count(*) FROM vale_decisao_vigente WHERE user_id = %s", (b,)
    ).fetchone() == (0,)
    # A segue intacto
    assert alocacao(situacao(conn, a.uid, "2025-02")) == (Decimal("200.00"), Decimal("950.00"))


def test_conta_de_outro_usuario_nao_recebe_bolso(conn: psycopg.Connection) -> None:
    """Uma despesa na conta de B nunca conta no consumo do VR de A, mesmo com bolso."""
    a, b = novo_vale(conn), novo_vale(conn)
    credito(conn, a.uid, a.vr, "2025-04-05", "1000.00")
    gasto(conn, b.uid, b.vr, "2025-04-10", "999.00", "trabalho")
    s = situacao(conn, a.uid, "2025-04")
    assert (s["consumo_trabalho"], s["consumo_pessoal"]) == (Decimal("0.00"), Decimal("0.00"))
    assert situacao(conn, b.uid, "2025-04")["consumo_trabalho"] == Decimal("999.00")
    # conta de usuário outro, conta própria mal escolhida
    c = conta(conn, a.uid, "corrente2")
    with Recusa(conn, "AB422"):
        parametro(conn, a.uid, c)
