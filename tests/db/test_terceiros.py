"""SPEC-007 (INV-10, 26, 32, 33; ADR 045): terceiros, repasse e a receber por pessoa.

Esperados de F-FAT-01, F-LIM-01 e F-REP-01..04 (fixtures/numericos.yaml), calculados à mão. As
datas dos cenários são deste arquivo (as fixtures não as trazem): fechamento no dia 10, compras em
2025-03-05 (primeira parcela na competência 2025-03, a segunda em 2025-04...), repasses depois.
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal

import psycopg
import pytest
from hypothesis import HealthCheck, given, settings
from hypothesis import strategies as st

from tests.db.test_estorno import (
    DATA_COMPRA,
    DATA_ESTORNO,
    Cenario,
    estornar,
    montar,
    pagar,
)
from tests.db.util_lancamento import (
    Recusa,
    cartao,
    compra,
    conta,
    excluir,
    lancar,
    linha_credito,
    versoes,
)
from tests.db.util_saldo import dec, fixture, novo_usuario, saldo
from tests.db.util_terceiros import (
    a_receber,
    a_receber_todas,
    contar_linhas,
    esperado_fatura,
    esperado_pessoa,
    excluir_pessoa,
    gravar_pessoa,
    nova_pessoa,
    reais,
    resumo_fatura,
)

pytestmark = pytest.mark.banco

DATA_REPASSE = "2025-03-20"
C1, C2, C3, C4 = "2025-03", "2025-04", "2025-05", "2025-06"


def _limite(conn: psycopg.Connection, c: Cenario, em: str) -> tuple[Decimal, Decimal, Decimal]:
    r = conn.execute(
        "SELECT limite, usado, disponivel FROM limite_linha(%s, %s, %s)",
        (c.uid, c.linha, date.fromisoformat(em)),
    ).fetchone()
    assert r is not None
    return r[0], r[1], r[2]


def _pessoas(conn: psycopg.Connection, uid: int, *chaves: str) -> dict[str, int]:
    return {k: nova_pessoa(conn, uid, k) for k in chaves}


def _montar_f_fat_01(conn: psycopg.Connection) -> tuple[Cenario, int]:
    f = fixture("F-FAT-01")
    c = montar(conn)
    b = nova_pessoa(conn, c.uid, "pessoa_b")
    for item in f["entrada"]["itens"]:
        pessoa = None if item["pessoa"] == "propria" else b
        compra(conn, c.uid, c.cartao, DATA_COMPRA, item["valor"], 1, pessoa=pessoa)
    for r in f["entrada"]["repasses"]:
        lancar(conn, c.uid, "repasse", DATA_REPASSE, c.corrente, r["valor"], pessoa=b)
    return c, b


def _montar_f_rep_03(conn: psycopg.Connection) -> tuple[Cenario, dict[str, int]]:
    f = fixture("F-REP-03")
    c = montar(conn)
    p = _pessoas(conn, c.uid, "pessoa_b", "pessoa_c", "pessoa_d", "pessoa_e", "pessoa_f")
    for item in f["entrada"]["compras"]:
        pessoa = None if item["pessoa"] == "propria" else p[item["pessoa"]]
        compra(conn, c.uid, c.cartao, DATA_COMPRA, item["total"], item["parcelas"], pessoa=pessoa)
    for r in f["entrada"]["repasses"]:
        lancar(conn, c.uid, "repasse", DATA_REPASSE, c.corrente, r["valor"], pessoa=p[r["pessoa"]])
    return c, p


# ---------------------------------------------------------------------------------------------
# SPEC-007-AC-1: a receber por pessoa
# ---------------------------------------------------------------------------------------------


def test_a_receber_f_fat_01(conn: psycopg.Connection) -> None:
    f = fixture("F-FAT-01")
    c, b = _montar_f_fat_01(conn)
    # D = 400,00 (a compra de terceiro), R = 250,00 -> a receber 150,00 e nenhum crédito
    assert a_receber(conn, c.uid, b) == (
        dec("400.00"),
        dec("250.00"),
        dec(f["esperado"]["a_receber_pessoa_b"]),
        dec("0.00"),
    )


def test_a_receber_varias_pessoas_f_rep_03(conn: psycopg.Connection) -> None:
    e = fixture("F-REP-03")["esperado"]
    c, p = _montar_f_rep_03(conn)
    todas = a_receber_todas(conn, c.uid)
    # as cinco pessoas aparecem, inclusive a sem movimento (f), em ordem de cadastro
    assert list(todas) == [
        p[k] for k in ("pessoa_b", "pessoa_c", "pessoa_d", "pessoa_e", "pessoa_f")
    ]
    for chave, pid in p.items():
        assert todas[pid] == esperado_pessoa(e[chave]), chave
    assert sum(v[2] for v in todas.values()) == dec(e["soma_a_receber"])
    assert sum(v[3] for v in todas.values()) == dec(e["soma_credito_da_pessoa"])
    # a consulta de uma pessoa só devolve ela
    assert a_receber_todas(conn, c.uid, p["pessoa_c"]) == {p["pessoa_c"]: todas[p["pessoa_c"]]}


# ---------------------------------------------------------------------------------------------
# SPEC-007-AC-4: fatura própria + terceiros e limite com terceiros
# ---------------------------------------------------------------------------------------------


def test_fatura_propria_mais_terceiros_f_fat_01(conn: psycopg.Connection) -> None:
    f = fixture("F-FAT-01")["esperado"]
    c, _ = _montar_f_fat_01(conn)
    total, propria, terceiros = resumo_fatura(conn, c.uid, c.cartao, C1)
    assert total == dec(f["fatura_total"])
    assert propria == dec(f["fatura_propria"])
    assert terceiros == dec("400.00")
    # o repasse não é parcela: não entra na fatura
    itens = conn.execute(
        "SELECT valor, pessoa_id IS NULL FROM fatura_itens(%s, %s, %s) ORDER BY valor",
        (c.uid, c.cartao, C1),
    ).fetchall()
    assert itens == [(dec("400.00"), False), (dec("600.00"), True)]


def test_limite_com_terceiros_f_lim_01(conn: psycopg.Connection) -> None:
    f = fixture("F-LIM-01")
    uid = novo_usuario(conn)
    linha, _ = linha_credito(conn, uid, "linha", f["entrada"]["linha"]["limite"])
    cartoes = {
        "X": cartao(conn, uid, "x", linha, 10, "2000-01-01"),
        "Y": cartao(conn, uid, "y", linha, 10, "2000-01-01"),
    }
    b = nova_pessoa(conn, uid, "pessoa_b")
    for item in f["entrada"]["compras"]:
        pessoa = None if item["pessoa"] == "propria" else b
        compra(
            conn, uid, cartoes[item["cartao"]], DATA_COMPRA, item["total"], item["parcelas"],
            pessoa=pessoa,
        )  # fmt: skip
    e = f["esperado"]
    r = conn.execute(
        "SELECT limite, usado, disponivel FROM limite_linha(%s, %s, %s)",
        (uid, linha, date.fromisoformat(DATA_COMPRA)),
    ).fetchone()
    # o limite conta o total da compra de terceiro (300,00) junto da própria (1200,00 em 4x)
    assert r == (
        dec(f["entrada"]["linha"]["limite"]),
        dec(e["limite_usado"]),
        dec(e["limite_disponivel"]),
    )
    assert a_receber(conn, uid, b)[0] == dec("300.00")


def test_fatura_e_limite_com_terceiros_f_rep_03(conn: psycopg.Connection) -> None:
    e = fixture("F-REP-03")["esperado"]
    c, _ = _montar_f_rep_03(conn)
    assert resumo_fatura(conn, c.uid, c.cartao, C1) == esperado_fatura(e["fatura_c1"])
    assert resumo_fatura(conn, c.uid, c.cartao, C2) == esperado_fatura(e["fatura_c2"])
    # a pessoa_c parcelou em 3: a terceira parcela cai em 2025-05 (30,00 de terceiro)
    assert resumo_fatura(conn, c.uid, c.cartao, C3) == (dec("30.00"), dec("0.00"), dec("30.00"))
    assert resumo_fatura(conn, c.uid, c.cartao, C4) == (dec("0.00"), dec("0.00"), dec("0.00"))
    limite = fixture("F-REP-03")["entrada"]["linha"]["limite"]
    assert _limite(conn, c, DATA_REPASSE) == (
        dec(limite),
        dec(e["limite_usado"]),
        dec(e["limite_disponivel"]),
    )


# ---------------------------------------------------------------------------------------------
# SPEC-007-AC-3: repasse excedente
# ---------------------------------------------------------------------------------------------


def test_repasse_excedente_f_rep_01(conn: psycopg.Connection) -> None:
    f = fixture("F-REP-01")
    e = f["esperado"]
    c = montar(conn)
    b = nova_pessoa(conn, c.uid, f["entrada"]["pessoa"])

    compra(conn, c.uid, c.cartao, DATA_COMPRA, "400.00", 1, pessoa=b)
    assert a_receber(conn, c.uid, b) == esperado_pessoa(e["apos_compra_400"])

    lancar(conn, c.uid, "repasse", DATA_REPASSE, c.corrente, "250.00", pessoa=b)
    assert a_receber(conn, c.uid, b) == esperado_pessoa(e["apos_repasse_250"])

    # repasse acima da dívida: aceito, o excedente vira crédito da pessoa
    lancar(conn, c.uid, "repasse", DATA_REPASSE, c.corrente, "200.00", pessoa=b)
    assert a_receber(conn, c.uid, b) == esperado_pessoa(e["apos_repasse_200"])
    assert saldo(conn, c.uid, c.corrente, "2025-03-31") == dec(
        e["saldo_corrente_apos_dois_repasses"]
    )

    # uma compra futura da pessoa abate o crédito sozinha
    compra(conn, c.uid, c.cartao, "2025-03-25", "30.00", 1, pessoa=b)
    assert a_receber(conn, c.uid, b) == esperado_pessoa(e["apos_compra_30"])
    compra(conn, c.uid, c.cartao, "2025-03-26", "100.00", 1, pessoa=b)
    assert a_receber(conn, c.uid, b) == esperado_pessoa(e["apos_compra_100"])


_CONFIG = settings(
    max_examples=30, deadline=None, suppress_health_check=[HealthCheck.function_scoped_fixture]
)


@_CONFIG
@given(
    compras=st.lists(
        st.tuples(
            st.integers(min_value=3, max_value=500_000), st.integers(min_value=1, max_value=3)
        ),
        max_size=3,
    ),
    repasses=st.lists(st.integers(min_value=1, max_value=900_000), max_size=3),
)
def test_a_receber_nunca_negativo(
    conn: psycopg.Connection, compras: list[tuple[int, int]], repasses: list[int]
) -> None:
    """INV-33: para quaisquer compras e repasses, a receber e crédito nunca são negativos, um dos
    dois é zero e D − R = a receber − crédito (D e R somados aqui, fora do banco)."""
    with conn.transaction(force_rollback=True):
        c = montar(conn)
        b = nova_pessoa(conn, c.uid, "pessoa_b")
        for centavos, n in compras:
            compra(conn, c.uid, c.cartao, DATA_COMPRA, reais(centavos), n, pessoa=b)
        for centavos in repasses:
            lancar(conn, c.uid, "repasse", DATA_REPASSE, c.corrente, reais(centavos), pessoa=b)
        d_total = sum(centavos for centavos, _ in compras)
        r_total = sum(repasses)

        divida, repassado, receber, credito = a_receber(conn, c.uid, b)
        assert divida == dec(reais(d_total))
        assert repassado == dec(reais(r_total))
        assert receber >= 0 and credito >= 0
        assert receber * credito == 0
        assert receber - credito == dec(reais(d_total)) - dec(reais(r_total))


# ---------------------------------------------------------------------------------------------
# SPEC-007-AC-5: estorno de compra de terceiro
# ---------------------------------------------------------------------------------------------


def _montar_f_rep_02(conn: psycopg.Connection) -> tuple[Cenario, int, int, int]:
    f = fixture("F-REP-02")["entrada"]
    c = montar(conn)
    b = nova_pessoa(conn, c.uid, "pessoa_b")
    t = f["compra_terceiro"]
    tid, versao, _ = compra(conn, c.uid, c.cartao, DATA_COMPRA, t["total"], t["parcelas"], pessoa=b)
    p = f["compra_propria"]
    compra(conn, c.uid, c.cartao, "2025-04-12", p["total"], p["parcelas"])  # cai em 2025-05
    lancar(conn, c.uid, "repasse", "2025-04-14", c.corrente, f["repasse"], pessoa=b)
    pagar(conn, c, f["pagamento"])
    return c, b, tid, versao


def test_estorno_de_compra_de_terceiro_f_rep_02(conn: psycopg.Connection) -> None:
    e = fixture("F-REP-02")["esperado"]
    c, b, tid, versao = _montar_f_rep_02(conn)
    assert a_receber(conn, c.uid, b) == esperado_pessoa(e["antes_do_estorno"])

    r = estornar(conn, c, tid, versao, DATA_ESTORNO)
    assert r.credito == dec(e["credito_na_fatura"])
    assert r.limite_devolvido == dec(e["limite_devolvido"])
    assert r.competencia == C3

    # D cai pelo T inteiro (400,00); o repasse de 100,00 vira crédito da pessoa
    assert a_receber(conn, c.uid, b) == esperado_pessoa(e["depois_do_estorno"])
    # faturas anteriores ao crédito não mudam; o crédito P fica no grupo de terceiros e a
    # fatura própria não é reduzida por ele
    for chave, comp in (("c1", C1), ("c2", C2), ("c3", C3), ("c4", C4)):
        assert resumo_fatura(conn, c.uid, c.cartao, comp) == esperado_fatura(e["faturas"][chave]), (
            chave
        )


def test_compra_de_terceiro_com_parte_paga_nao_e_editavel(conn: psycopg.Connection) -> None:
    """ADR 044 itens 8 e 9 valem igual para terceiros; a recusa não grava nem muda o a receber."""
    c, b, tid, versao = _montar_f_rep_02(conn)
    antes = a_receber(conn, c.uid, b)
    with Recusa(conn, "AB422"):
        compra(conn, c.uid, c.cartao, DATA_COMPRA, "400.00", 4, pessoa=None,
               transacao_id=tid, versao=versao)  # fmt: skip
    with Recusa(conn, "AB422"):
        excluir(conn, c.uid, tid, versao)
    assert a_receber(conn, c.uid, b) == antes
    # depois do estorno o cartão fica imutável (ADR 044 item 9)
    estornar(conn, c, tid, versao, DATA_ESTORNO)
    with Recusa(conn, "AB422"):
        excluir(conn, c.uid, tid, versao)


# ---------------------------------------------------------------------------------------------
# SPEC-007-AC-2: divisão rejeitada (F-REP-04)
# ---------------------------------------------------------------------------------------------


def test_divisao_rejeitada_no_esquema(conn: psycopg.Connection) -> None:
    e = fixture("F-REP-04")["esperado"]
    c = montar(conn)
    b = nova_pessoa(conn, c.uid, "pessoa_b")
    outra = nova_pessoa(conn, c.uid, "pessoa_c")

    # a função recebe uma pessoa por compra: 100% de terceiro é aceita (e vira dívida dela)
    compra(conn, c.uid, c.cartao, DATA_COMPRA, "100.00", 1, pessoa=b)
    assert a_receber(conn, c.uid, b) == esperado_pessoa(e["pessoa_b"])
    antes = contar_linhas(conn, c.uid)

    # direto nas linhas (nem o dono grava): parcelas da mesma compra com pessoas diferentes, ou
    # parte própria e parte de terceiro, são barradas pelo gatilho de pernas
    conn.execute("SET CONSTRAINTS transacao_pernas_ck IMMEDIATE")
    for pessoas in ((b, None), (None, b), (b, outra)):
        tid = conn.execute("SELECT nextval('transacao_id_seq')").fetchone()
        assert tid is not None
        with pytest.raises(psycopg.errors.CheckViolation), conn.transaction():
            conn.execute(
                "INSERT INTO transacao_versao (user_id, transacao_id, conta_id, data_transacao, "
                "valor, tipo, perna, parcela, competencia, pessoa_id) VALUES "
                "(%s, %s, %s, DATE '2025-03-05', -60.00, 'credito', 1, 1, '2025-03', %s::bigint), "
                "(%s, %s, %s, DATE '2025-03-05', -40.00, 'credito', 1, 2, '2025-04', %s::bigint)",
                (c.uid, tid[0], c.cartao, pessoas[0], c.uid, tid[0], c.cartao, pessoas[1]),
            )
    assert contar_linhas(conn, c.uid) == antes
    assert a_receber(conn, c.uid, b) == esperado_pessoa(e["pessoa_b"])
    assert e["lancamentos_gravados_pelas_recusadas"] == 0


def test_pessoa_so_em_compra_a_credito_e_repasse(conn: psycopg.Connection) -> None:
    c = montar(conn)
    b = nova_pessoa(conn, c.uid, "pessoa_b")
    outra = conta(conn, c.uid, "outra corrente")
    antes = contar_linhas(conn, c.uid)

    # terceiro fora do cartão: débito, receita, transferência, rendimento (F-REP-04, 2ª tentativa)
    with Recusa(conn, "AB422"):
        lancar(conn, c.uid, "debito", DATA_COMPRA, c.corrente, "100.00", pessoa=b)
    with Recusa(conn, "AB422"):
        lancar(conn, c.uid, "receita", DATA_COMPRA, c.corrente, "100.00", pessoa=b)
    with Recusa(conn, "AB422"):
        lancar(
            conn, c.uid, "transferencia", DATA_COMPRA, c.corrente, "10.00", destino=outra, pessoa=b
        )
    with Recusa(conn, "AB422"):
        lancar(
            conn,
            c.uid,
            "rendimento",
            DATA_COMPRA,
            c.corrente,
            bruto="10.00",
            imposto="1.00",
            pessoa=b,
        )
    # repasse sem pessoa; e o esquema barra repasse/débito sem ou com pessoa fora da regra
    with Recusa(conn, "AB422"):
        lancar(conn, c.uid, "repasse", DATA_REPASSE, c.corrente, "10.00")
    for tipo, valor, pessoa in (("repasse", 10, None), ("debito", -10, b), ("receita", 10, b)):
        with pytest.raises(psycopg.errors.CheckViolation), conn.transaction():
            conn.execute(
                "INSERT INTO transacao_versao (user_id, conta_id, data_transacao, valor, tipo, "
                "pessoa_id) VALUES (%s, %s, DATE '2025-03-05', %s, %s, %s::bigint)",
                (c.uid, c.corrente, valor, tipo, pessoa),
            )
    # repasse com valor negativo também é barrado no esquema (sinal)
    with pytest.raises(psycopg.errors.CheckViolation), conn.transaction():
        conn.execute(
            "INSERT INTO transacao_versao (user_id, conta_id, data_transacao, valor, tipo, "
            "pessoa_id) VALUES (%s, %s, DATE '2025-03-05', -10, 'repasse', %s)",
            (c.uid, c.corrente, b),
        )
    assert contar_linhas(conn, c.uid) == antes
    # a compra sem pessoa continua própria
    compra(conn, c.uid, c.cartao, DATA_COMPRA, "10.00", 1)
    assert a_receber(conn, c.uid, b) == (dec("0.00"),) * 4


# ---------------------------------------------------------------------------------------------
# SPEC-007-AC-8: repasse é tipo próprio
# ---------------------------------------------------------------------------------------------


def test_repasse_regras_de_entrada(conn: psycopg.Connection) -> None:
    c = montar(conn)
    b = nova_pessoa(conn, c.uid, "pessoa_b")
    reserva = conta(conn, c.uid, "caixinha", "reserva", mae=c.corrente)
    vale = conta(conn, c.uid, "vale", "beneficio")
    antes = contar_linhas(conn, c.uid)

    # só conta corrente
    for destino in (reserva, vale, c.cartao):
        with Recusa(conn, "AB422"):
            lancar(conn, c.uid, "repasse", DATA_REPASSE, destino, "10.00", pessoa=b)
    amanha = conn.execute(
        "SELECT ((now() AT TIME ZONE 'America/Sao_Paulo')::date + 1)::text"
    ).fetchone()
    assert amanha is not None
    with Recusa(conn, "AB422"):
        lancar(conn, c.uid, "repasse", amanha[0], c.corrente, "10.00", pessoa=b)
    for valor in ("0.00", "-5.00", "1.005", None):
        with Recusa(conn, "AB422"):
            lancar(conn, c.uid, "repasse", DATA_REPASSE, c.corrente, valor, pessoa=b)
    with Recusa(conn, "AB404"):
        lancar(conn, c.uid, "repasse", DATA_REPASSE, c.corrente, "10.00", pessoa=987654321)
    assert contar_linhas(conn, c.uid) == antes

    lancar(conn, c.uid, "repasse", DATA_REPASSE, c.corrente, "250.00", pessoa=b)
    # sobe o saldo da conta; é tipo repasse (não receita) e positivo
    assert saldo(conn, c.uid, c.corrente, "2025-03-31") == dec("250.00")
    tipos = conn.execute(
        "SELECT tipo, valor, pessoa_id FROM lancamento_vigente WHERE user_id = %s", (c.uid,)
    ).fetchall()
    assert tipos == [("repasse", dec("250.00"), b)]
    # não é compra: nada de fatura, parcela ativa nem limite
    assert resumo_fatura(conn, c.uid, c.cartao, C1) == (dec("0.00"),) * 3
    assert _limite(conn, c, DATA_REPASSE)[1] == dec("0.00")
    n_parcelas = conn.execute(
        "SELECT count(*) FROM parcela_ativa WHERE user_id = %s", (c.uid,)
    ).fetchone()
    assert n_parcelas == (0,)


def test_repasse_edita_e_exclui_com_versao(conn: psycopg.Connection) -> None:
    c = montar(conn)
    b = nova_pessoa(conn, c.uid, "pessoa_b")
    compra(conn, c.uid, c.cartao, DATA_COMPRA, "400.00", 1, pessoa=b)
    tid, versao, _ = lancar(conn, c.uid, "repasse", DATA_REPASSE, c.corrente, "250.00", pessoa=b)
    assert a_receber(conn, c.uid, b)[2] == dec("150.00")

    # edição = nova versão; a anterior fica no histórico e não conta
    tid2, versao2, _ = lancar(
        conn, c.uid, "repasse", DATA_REPASSE, c.corrente, "100.00", pessoa=b,
        transacao_id=tid, versao=versao,
    )  # fmt: skip
    assert (tid2, versao2) == (tid, 2)
    assert [(v.versao, v.vigente) for v in versoes(conn, c.uid, tid)] == [(1, False), (2, True)]
    assert a_receber(conn, c.uid, b)[2] == dec("300.00")
    with Recusa(conn, "AB409"):  # versão desatualizada
        lancar(conn, c.uid, "repasse", DATA_REPASSE, c.corrente, "1.00", pessoa=b,
               transacao_id=tid, versao=versao)  # fmt: skip

    # exclusão lógica devolve o a receber ao que era sem o repasse
    assert excluir(conn, c.uid, tid, versao2) == 3
    assert a_receber(conn, c.uid, b) == (dec("400.00"), dec("0.00"), dec("400.00"), dec("0.00"))
    assert saldo(conn, c.uid, c.corrente, "2025-03-31") == dec("0.00")
    with Recusa(conn, "AB404"):
        lancar(conn, c.uid, "repasse", DATA_REPASSE, c.corrente, "5.00", pessoa=b,
               transacao_id=tid, versao=3)  # fmt: skip


# ---------------------------------------------------------------------------------------------
# SPEC-007-AC-9: cadastro de pessoa
# ---------------------------------------------------------------------------------------------


def test_cadastro_de_pessoa_versiona(conn: psycopg.Connection) -> None:
    uid = novo_usuario(conn)
    pid, v1 = gravar_pessoa(conn, uid, "  Pessoa B ")
    assert v1 == 1
    assert gravar_pessoa(conn, uid, "Pessoa Bb", pid, v1) == (pid, 2)
    historico = conn.execute(
        "SELECT versao, vigente, excluida FROM pessoa WHERE user_id = %s AND pessoa_id = %s "
        "ORDER BY versao",
        (uid, pid),
    ).fetchall()
    assert historico == [(1, False, False), (2, True, False)]
    nome = conn.execute(
        "SELECT nome FROM pessoa WHERE user_id = %s AND pessoa_id = %s AND vigente", (uid, pid)
    ).fetchone()
    assert nome == ("Pessoa Bb",)  # sem espaços nas pontas

    with Recusa(conn, "AB409"):  # versão desatualizada
        gravar_pessoa(conn, uid, "outro", pid, v1)
    with Recusa(conn, "AB422"):  # editar exige a versão lida
        gravar_pessoa(conn, uid, "outro", pid, None)
    for ruim in ("", "   ", None, "x" * 81):
        with Recusa(conn, "AB422"):
            gravar_pessoa(conn, uid, ruim)
    with Recusa(conn, "AB410"):  # nome repetido, sem diferenciar maiúsculas
        gravar_pessoa(conn, uid, "PESSOA BB")
    # o nome antigo ficou livre com a renomeação
    outro, _ = gravar_pessoa(conn, uid, "pessoa b")
    assert outro != pid
    # usuários diferentes podem ter o mesmo nome
    gravar_pessoa(conn, novo_usuario(conn), "Pessoa Bb")


def test_exclusao_de_pessoa_recusada_com_movimento(conn: psycopg.Connection) -> None:
    c = montar(conn)
    b, vb = gravar_pessoa(conn, c.uid, "pessoa_b")
    d, vd = gravar_pessoa(conn, c.uid, "pessoa_d")
    tid, tv, _ = compra(conn, c.uid, c.cartao, DATA_COMPRA, "40.00", 2, pessoa=b)
    rid, rv, _ = lancar(conn, c.uid, "repasse", DATA_REPASSE, c.corrente, "5.00", pessoa=d)

    with Recusa(conn, "AB422"):  # tem compra
        excluir_pessoa(conn, c.uid, b, vb)
    with Recusa(conn, "AB422"):  # tem só repasse
        excluir_pessoa(conn, c.uid, d, vd)
    with Recusa(conn, "AB409"):
        excluir_pessoa(conn, c.uid, d, vd + 1)
    assert set(a_receber_todas(conn, c.uid)) == {b, d}

    # sem movimento vigente (lançamentos excluídos), a pessoa sai: some da lista e o nome é liberado
    excluir(conn, c.uid, tid, tv)
    excluir(conn, c.uid, rid, rv)
    assert excluir_pessoa(conn, c.uid, b, vb) == vb + 1
    assert excluir_pessoa(conn, c.uid, d, vd) == vd + 1
    assert a_receber_todas(conn, c.uid) == {}
    gravar_pessoa(conn, c.uid, "pessoa_b")  # nome livre de novo
    with Recusa(conn, "AB404"):  # pessoa excluída não recebe mais lançamentos
        compra(conn, c.uid, c.cartao, DATA_COMPRA, "10.00", 1, pessoa=b)
    with Recusa(conn, "AB404"):
        excluir_pessoa(conn, c.uid, b, vb + 1)
    with Recusa(conn, "AB404"):
        gravar_pessoa(conn, c.uid, "volta", b, vb + 1)


# ---------------------------------------------------------------------------------------------
# SPEC-007-AC-6: isolamento
# ---------------------------------------------------------------------------------------------


def test_leituras_nao_vazam_para_outro_usuario(conn: psycopg.Connection) -> None:
    c, p = _montar_f_rep_03(conn)
    outro = novo_usuario(conn)
    meu, _ = gravar_pessoa(conn, outro, "pessoa_b")

    # o outro usuário consulta com o id de uma pessoa do primeiro: nada
    assert a_receber_todas(conn, outro, p["pessoa_b"]) == {}
    # e vê só a própria pessoa, zerada, sem os valores do primeiro
    assert a_receber_todas(conn, outro) == {meu: (dec("0.00"),) * 4}
    for comp in (C1, C2):
        assert resumo_fatura(conn, outro, c.cartao, comp) == (dec("0.00"),) * 3
    itens = conn.execute(
        "SELECT count(*) FROM fatura_itens(%s, %s, %s)", (outro, c.cartao, C1)
    ).fetchone()
    assert itens == (0,)
    # o primeiro continua com os próprios valores
    assert a_receber(conn, c.uid, p["pessoa_b"])[2] == dec("150.00")
    assert resumo_fatura(conn, c.uid, c.cartao, C1)[0] == dec("1090.00")


def test_pessoa_de_outro_usuario_nao_existe_para_mim(conn: psycopg.Connection) -> None:
    c = montar(conn)
    alheia, v = gravar_pessoa(conn, novo_usuario(conn), "pessoa_alheia")
    antes = contar_linhas(conn, c.uid)
    with Recusa(conn, "AB404"):
        compra(conn, c.uid, c.cartao, DATA_COMPRA, "10.00", 1, pessoa=alheia)
    with Recusa(conn, "AB404"):
        lancar(conn, c.uid, "repasse", DATA_REPASSE, c.corrente, "10.00", pessoa=alheia)
    with Recusa(conn, "AB404"):
        gravar_pessoa(conn, c.uid, "roubada", alheia, v)
    with Recusa(conn, "AB404"):
        excluir_pessoa(conn, c.uid, alheia, v)
    assert contar_linhas(conn, c.uid) == antes


# ---------------------------------------------------------------------------------------------
# SPEC-007-AC-7 e AC-10: nome fora do pipeline e das leituras; papéis
# ---------------------------------------------------------------------------------------------


def test_nome_da_pessoa_fora_do_pipeline_e_das_leituras(
    conn: psycopg.Connection, url_pipeline: str
) -> None:
    c, _ = _montar_f_rep_03(conn)
    # as leituras devolvem só ids e valores; o nome é resolvido na borda da API
    for consulta, args in (
        ("SELECT * FROM a_receber_pessoas(%s, NULL)", (c.uid,)),
        ("SELECT * FROM fatura_itens(%s, %s, %s)", (c.uid, c.cartao, C1)),
        ("SELECT * FROM fatura_resumo(%s, %s, %s)", (c.uid, c.cartao, C1)),
    ):
        cur = conn.execute(consulta, args)
        colunas = [col.name for col in cur.description or []]
        assert colunas and not any("nome" in col for col in colunas), colunas
    for visao in ("transacao_vigente", "lancamento_vigente", "parcela_ativa", "parcela_fatura"):
        achado = conn.execute(
            "SELECT count(*) FROM information_schema.columns "
            "WHERE table_name = %s AND column_name = 'nome'",
            (visao,),
        ).fetchone()
        assert achado == (0,), visao

    with psycopg.connect(url_pipeline) as pipe:
        privs = pipe.execute(
            "SELECT has_column_privilege('pessoa', 'nome', 'SELECT'), "
            "has_column_privilege('pessoa', 'pessoa_id', 'SELECT'), "
            "has_column_privilege('pessoa', 'user_id', 'SELECT')"
        ).fetchone()
        assert privs == (False, True, True)
        with pytest.raises(psycopg.errors.InsufficientPrivilege):
            pipe.execute("SELECT nome FROM pessoa")
        pipe.rollback()
        with pytest.raises(psycopg.errors.InsufficientPrivilege):
            pipe.execute("SELECT * FROM pessoa")
        pipe.rollback()
        pipe.execute("SELECT pessoa_id, user_id, vigente FROM pessoa").fetchall()
        pipe.execute("SELECT pessoa_id FROM transacao_vigente").fetchall()


FUNCOES_DO_APP = (
    "pessoa_gravar(bigint, bigint, integer, text)",
    "pessoa_excluir(bigint, bigint, integer)",
    "a_receber_pessoas(bigint, bigint)",
    "fatura_resumo(bigint, bigint, text)",
    "fatura_itens(bigint, bigint, text)",
    "lancamento_gravar(bigint, bigint, integer, text, date, numeric, bigint, bigint, numeric, "
    "numeric, text, text, text, integer, bigint, text)",
)


LEITURAS_DO_PIPELINE = (
    "a_receber_pessoas(bigint, bigint)",
    "fatura_resumo(bigint, bigint, text)",
    "fatura_itens(bigint, bigint, text)",
)


def test_papeis_da_pessoa(esquema: str, url_app: str, url_pipeline: str) -> None:
    with psycopg.connect(url_app) as app, psycopg.connect(url_pipeline) as pipe:
        for funcao in FUNCOES_DO_APP:
            assert app.execute(
                "SELECT has_function_privilege(%s, 'EXECUTE')", (funcao,)
            ).fetchone() == (True,), funcao
            # 0014 / ADR 054: o pipeline lê a receber, fatura e resumo (INVOKER); nunca escreve
            assert pipe.execute(
                "SELECT has_function_privilege(%s, 'EXECUTE')", (funcao,)
            ).fetchone() == (funcao in LEITURAS_DO_PIPELINE,), funcao
        assert app.execute(
            "SELECT has_function_privilege("
            "'lancamento_gravar_base(bigint, bigint, integer, text, date, numeric, bigint, bigint, "
            "numeric, numeric, text, text, text, integer, bigint)', 'EXECUTE')"
        ).fetchone() == (False,)
        for priv in ("INSERT", "UPDATE", "DELETE", "TRUNCATE"):
            assert app.execute(
                "SELECT has_table_privilege(current_user, 'pessoa', %s)", (priv,)
            ).fetchone() == (False,), priv
            assert pipe.execute(
                "SELECT has_table_privilege(current_user, 'pessoa', %s)", (priv,)
            ).fetchone() == (False,), priv
        assert app.execute(
            "SELECT has_table_privilege(current_user, 'pessoa', 'SELECT')"
        ).fetchone() == (True,)
        for comando in (
            "INSERT INTO pessoa (user_id, nome) VALUES (1, 'x')",
            "UPDATE pessoa SET nome = 'y'",
            "DELETE FROM pessoa",
        ):
            with pytest.raises(psycopg.errors.InsufficientPrivilege):
                app.execute(comando)
            app.rollback()

        # o app escreve pelas funções (SECURITY DEFINER) e lê o que escreveu; nada fica no banco
        uid = app.execute(
            "INSERT INTO usuario (login) VALUES ('u_papel_pessoa') RETURNING user_id"
        ).fetchone()
        assert uid is not None
        u = uid[0]
        pid, _ = gravar_pessoa(app, u, "pessoa_papel")
        corrente = conta(app, u, "corrente")
        lancar(app, u, "repasse", DATA_REPASSE, corrente, "10.00", pessoa=pid)
        assert a_receber(app, u, pid) == (dec("0.00"), dec("10.00"), dec("0.00"), dec("10.00"))
        app.rollback()
        with pytest.raises(psycopg.errors.InsufficientPrivilege):
            pipe.execute("SELECT pessoa_gravar(1, NULL, NULL, 'x')")
        pipe.rollback()


def test_leituras_com_user_id_de_outro_usuario_devolvem_vazio(conn: psycopg.Connection) -> None:
    """INV-13: a_receber_pessoas, fatura_itens e fatura_resumo chamados com o user_id de OUTRO
    usuário e com os ids (pessoa, cartão) do primeiro devolvem vazio/zero, nos dois sentidos."""
    c, p = _montar_f_rep_03(conn)
    outro = novo_usuario(conn)
    assert a_receber_todas(conn, outro, p["pessoa_b"]) == {}
    assert a_receber_todas(conn, outro, p["pessoa_c"]) == {}
    for comp in (C1, C2):
        assert resumo_fatura(conn, outro, c.cartao, comp) == (dec("0.00"),) * 3
        itens = conn.execute(
            "SELECT count(*) FROM fatura_itens(%s, %s, %s)", (outro, c.cartao, comp)
        ).fetchone()
        assert itens == (0,)
    # sentido inverso: o primeiro com ids que não são dele (pessoa e cartão do outro)
    alheia, _ = gravar_pessoa(conn, outro, "pessoa_alheia")
    assert a_receber_todas(conn, c.uid, alheia) == {}
    assert resumo_fatura(conn, c.uid, c.cartao + 10**6, C1) == (dec("0.00"),) * 3
