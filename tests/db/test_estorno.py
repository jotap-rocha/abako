"""SPEC-006 (INV-08, ADR 044): estorno da compra a crédito, alocação do pago e recusas.

Esperados de F-EST-01..06 (fixtures/numericos.yaml), calculados à mão. As datas dos cenários são
deste arquivo (as fixtures não as trazem): fechamento no dia 10, compra em 2025-03-05
(competências 2025-03..2025-06), pagamentos em 2025-04-15 e estorno em 2025-04-20, que cai na
fatura 2025-05 (dia 20 >= fechamento).
"""

from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import date, timedelta
from decimal import Decimal

import psycopg
import pytest
from hypothesis import HealthCheck, given, settings
from hypothesis import strategies as st

from tests.db.util_lancamento import (
    Recusa,
    ano_atras,
    apagar_usuario,
    cartao,
    compra,
    conta,
    corrida,
    excluir,
    fechar,
    lancar,
    linha_credito,
    parcelas_da,
)
from tests.db.util_saldo import dec, dia, fixture, novo_usuario, saldo

pytestmark = pytest.mark.banco

DATA_COMPRA = "2025-03-05"
DATA_PAGAMENTO = "2025-04-15"
DATA_ESTORNO = "2025-04-20"
COMPETENCIA_CREDITO = "2025-05"


@dataclass(frozen=True)
class Cenario:
    uid: int
    corrente: int
    linha: int
    cartao: int


@dataclass(frozen=True)
class Estorno:
    id: int
    competencia: str
    total: Decimal
    credito: Decimal
    limite_devolvido: Decimal


def montar(conn: psycopg.Connection) -> Cenario:
    uid = novo_usuario(conn)
    corrente = conta(conn, uid, "corrente")
    linha, _ = linha_credito(conn, uid, "linha", "5000.00")
    return Cenario(uid, corrente, linha, cartao(conn, uid, "cartao", linha, 10, "2000-01-01"))


def pagar(conn: psycopg.Connection, c: Cenario, valor: str, data: str = DATA_PAGAMENTO) -> int:
    tid, _, _ = lancar(conn, c.uid, "transferencia", data, c.corrente, valor, destino=c.cartao)
    return tid


def estornar(
    conn: psycopg.Connection, c: Cenario, tid: int, versao: int = 1, data: str = DATA_ESTORNO
) -> Estorno:
    linha = conn.execute(
        "SELECT estorno_id, competencia_credito, total, credito, limite_devolvido "
        "FROM estorno_gravar(%s, %s, %s, %s, NULL)",
        (c.uid, tid, versao, dia(data)),
    ).fetchone()
    assert linha is not None
    return Estorno(*linha)


def fatura(conn: psycopg.Connection, c: Cenario, competencia: str) -> Decimal:
    linha = conn.execute(
        "SELECT fatura_total(%s, %s, %s)", (c.uid, c.cartao, competencia)
    ).fetchone()
    assert linha is not None
    total: Decimal = linha[0]
    return total


def usado(conn: psycopg.Connection, c: Cenario, em: str) -> Decimal:
    linha = conn.execute(
        "SELECT usado FROM limite_linha(%s, %s, %s)", (c.uid, c.linha, dia(em))
    ).fetchone()
    assert linha is not None
    valor: Decimal = linha[0]
    return valor


def pool(conn: psycopg.Connection, c: Cenario) -> Decimal:
    linha = conn.execute("SELECT pool_pago(%s, %s)", (c.uid, c.cartao)).fetchone()
    assert linha is not None
    valor: Decimal = linha[0]
    return valor


def alocado(conn: psycopg.Connection, c: Cenario) -> list[tuple[int, int, Decimal]]:
    """(transacao_id, parcela, alocado) na ordem de alocação."""
    linhas = conn.execute(
        "SELECT transacao_id, parcela, alocado FROM alocacao_pago(%s, %s)", (c.uid, c.cartao)
    ).fetchall()
    return [(int(r[0]), int(r[1]), r[2]) for r in linhas]


@dataclass(frozen=True)
class Foto:
    """Saldo do cartão e limite usado num instante, para medir o efeito do estorno."""

    saldo: Decimal
    usado: Decimal


def foto(conn: psycopg.Connection, c: Cenario, em: str) -> Foto:
    return Foto(saldo(conn, c.uid, c.cartao, em), usado(conn, c, em))


def liquido(
    conn: psycopg.Connection, c: Cenario, antes: Foto, total: Decimal | str, em: str
) -> Decimal:
    """Líquido da compra medido no banco: -T + o que o estorno devolveu (saldo e limite).

    Não usa os campos devolvidos por `estorno_gravar`: lê o saldo do cartão e o limite usado
    antes e depois e exige que os dois caminhos concordem.
    """
    depois = foto(conn, c, em)
    via_saldo = -dec(str(total)) + (depois.saldo - antes.saldo)
    via_limite = -dec(str(total)) + (antes.usado - depois.usado)
    assert via_saldo == via_limite
    return via_saldo


def pago_da(conn: psycopg.Connection, c: Cenario, tid: int) -> Decimal:
    linha = conn.execute("SELECT pago FROM compra_paga(%s, %s)", (c.uid, tid)).fetchone()
    assert linha is not None
    valor: Decimal = linha[0]
    return valor


@contextmanager
def recusa_com(conn: psycopg.Connection, codigo: str, trecho: str) -> Iterator[None]:
    """Espera a recusa `codigo` cuja mensagem contém `trecho`; desfaz só a tentativa."""
    with pytest.raises(psycopg.Error) as info:
        with conn.transaction():
            yield
    assert info.value.sqlstate == codigo, (info.value.sqlstate, str(info.value))
    assert trecho in str(info.value), str(info.value)


def _reais(centavos: int) -> str:
    return f"{centavos // 100}.{centavos % 100:02d}"


# ---------------------------------------------------------------------------------------------
# F-EST-01 a F-EST-05
# ---------------------------------------------------------------------------------------------


def test_f_est_01(conn: psycopg.Connection) -> None:
    """SPEC-006-AC-1: estorno integral devolve o limite todo e não mexe na conta corrente."""
    f = fixture("F-EST-01")
    ent, e = f["entrada"]["compra"], f["esperado"]
    c = montar(conn)
    tid, versao, _ = compra(conn, c.uid, c.cartao, DATA_COMPRA, ent["total"], ent["parcelas"])
    data = "2025-03-08"  # antes do fechamento (dia 10): a fatura 2025-03 ainda está aberta
    fatura_antes = fatura(conn, c, "2025-03")
    corrente_antes = saldo(conn, c.uid, c.corrente, data)
    assert usado(conn, c, data) == dec(ent["total"])

    antes = foto(conn, c, data)
    r = estornar(conn, c, tid, versao, data)

    assert r.limite_devolvido == dec(e["limite_devolvido"])
    assert r.credito == dec("0.00")  # nada pago: não há crédito
    assert fatura_antes - fatura(conn, c, "2025-03") == dec(e["reduz_fatura_aberta"])
    assert saldo(conn, c.uid, c.corrente, data) - corrente_antes == dec(
        e["movimento_em_conta_corrente"]
    )
    assert usado(conn, c, data) == dec("0.00")  # o limite voltou por inteiro
    assert liquido(conn, c, antes, ent["total"], data) == dec(e["liquido_da_compra"])
    # a linha do estorno está só no cartão: nenhuma perna em conta corrente
    contas = conn.execute(
        "SELECT conta_id FROM transacao_versao WHERE user_id = %s AND transacao_id = %s",
        (c.uid, r.id),
    ).fetchall()
    assert contas == [(c.cartao,)]


def test_f_est_02(conn: psycopg.Connection) -> None:
    """SPEC-006-AC-2: com 1 parcela paga, o pago vira crédito na próxima fatura aberta."""
    f = fixture("F-EST-02")
    ent, e = f["entrada"]["compra"], f["esperado"]
    c = montar(conn)
    tid, versao, _ = compra(conn, c.uid, c.cartao, DATA_COMPRA, ent["total"], ent["parcelas"])
    pagar(conn, c, "100.00")  # a parcela 1 (ent["pagas"] = 1) fica quitada
    corrente_antes = saldo(conn, c.uid, c.corrente, DATA_ESTORNO)
    antes = foto(conn, c, DATA_ESTORNO)

    r = estornar(conn, c, tid, versao)

    assert r.limite_devolvido == dec(e["limite_devolvido"])
    assert r.credito == dec(e["credito_proxima_fatura_aberta"])
    assert r.competencia == COMPETENCIA_CREDITO
    assert fatura(conn, c, COMPETENCIA_CREDITO) == -dec(e["credito_proxima_fatura_aberta"])
    itens = conn.execute(
        "SELECT valor FROM fatura_itens(%s, %s, %s)", (c.uid, c.cartao, COMPETENCIA_CREDITO)
    ).fetchall()
    assert itens == [(dec("-100.00"),)]  # só o crédito: as parcelas da compra saíram da fatura
    assert saldo(conn, c.uid, c.corrente, DATA_ESTORNO) - corrente_antes == dec(
        e["movimento_em_conta_corrente"]
    )
    assert liquido(conn, c, antes, ent["total"], DATA_ESTORNO) == dec(e["liquido_da_compra"])


def test_f_est_03(conn: psycopg.Connection) -> None:
    """SPEC-006-AC-4: parcela paga em parte gera crédito só da parte paga."""
    f = fixture("F-EST-03")
    ent, e = f["entrada"]["compra"], f["esperado"]
    c = montar(conn)
    tid, versao, _ = compra(conn, c.uid, c.cartao, DATA_COMPRA, ent["total"], ent["parcelas"])
    pagar(conn, c, f["entrada"]["pagamentos"][0])
    assert saldo(conn, c.uid, c.cartao, DATA_ESTORNO) == dec(e["saldo_cartao_antes"])
    # parcela 1 quitada (100), parcela 2 paga em parte (50), as outras sem nada (descrição)
    assert [a for _, _, a in alocado(conn, c)] == [dec(x) for x in ("100", "50", "0", "0")]
    assert pago_da(conn, c, tid) == dec(e["pago_alocado"])
    antes = foto(conn, c, DATA_ESTORNO)

    r = estornar(conn, c, tid, versao)

    assert r.limite_devolvido == dec(e["limite_devolvido"])
    assert r.credito == dec(e["credito_proxima_fatura_aberta"])
    assert saldo(conn, c.uid, c.cartao, DATA_ESTORNO) == dec(e["saldo_cartao_depois"])
    assert liquido(conn, c, antes, ent["total"], DATA_ESTORNO) == dec(e["liquido_da_compra"])


def _duas_compras(conn: psycopg.Connection) -> tuple[Cenario, int, int, int, int]:
    f = fixture("F-EST-04")
    a, b = f["entrada"]["compra_A"], f["entrada"]["compra_B"]
    c = montar(conn)
    ta, va, _ = compra(conn, c.uid, c.cartao, ano_atras(a["data"]), a["total"], a["parcelas"])
    tb, vb, _ = compra(conn, c.uid, c.cartao, ano_atras(b["data"]), b["total"], b["parcelas"])
    # as competências da fixture saem do fechamento do cenário
    assert [comp for _, comp in parcelas_da(conn, c.uid, ta)][0] == ano_atras(
        a["primeira_competencia"]
    )
    assert [comp for _, comp in parcelas_da(conn, c.uid, tb)] == [ano_atras(b["competencia"])]
    pagar(conn, c, f["entrada"]["pagamentos"][0])
    return c, ta, va, tb, vb


def test_f_est_04(conn: psycopg.Connection) -> None:
    """SPEC-006-AC-5: alocação por competência, data da compra e parcela; crédito sai do pool."""
    f = fixture("F-EST-04")
    caso_b, caso_a = f["casos"]
    assert (caso_b["estorno"], caso_a["estorno"]) == ("B", "A")

    # Alocação antes de qualquer estorno: A1 100, A2 100, B 50 (a ordem da fixture).
    c, ta, _, tb, _ = _duas_compras(conn)
    assert alocado(conn, c) == [
        (ta, 1, dec("100")),
        (ta, 2, dec("100")),
        (tb, 1, dec("50")),
        (ta, 3, dec("0")),
        (ta, 4, dec("0")),
    ]

    # Estorno de B: P = 50; o pool cai a 200 e continua cobrindo A1 e A2.
    c, ta, _, tb, vb = _duas_compras(conn)
    antes = foto(conn, c, DATA_ESTORNO)
    r = estornar(conn, c, tb, vb)
    assert pago_da(conn, c, ta) == dec("200.00")
    assert r.credito == dec(caso_b["credito_proxima_fatura_aberta"])
    assert r.limite_devolvido == dec(caso_b["limite_devolvido"])
    assert pool(conn, c) == dec("200.00")
    total_b = fixture("F-EST-04")["entrada"]["compra_B"]["total"]
    assert liquido(conn, c, antes, total_b, DATA_ESTORNO) == dec(caso_b["liquido_da_compra"])

    # Estorno de A: P = 200; o pool cai a 50 e passa para B.
    c, ta, va, tb, _ = _duas_compras(conn)
    antes = foto(conn, c, DATA_ESTORNO)
    r = estornar(conn, c, ta, va)
    assert r.credito == dec(caso_a["credito_proxima_fatura_aberta"])
    assert r.limite_devolvido == dec(caso_a["limite_devolvido"])
    assert pago_da(conn, c, tb) == dec(caso_a["pago_alocado_a_B_depois"])
    total_a = fixture("F-EST-04")["entrada"]["compra_A"]["total"]
    assert liquido(conn, c, antes, total_a, DATA_ESTORNO) == dec(caso_a["liquido_da_compra"])


def test_f_est_05(conn: psycopg.Connection) -> None:
    """SPEC-006-AC-7: pagamento maior que a dívida; o excedente fica no pool."""
    f = fixture("F-EST-05")
    ent, e = f["entrada"]["compra"], f["esperado"]
    c = montar(conn)
    tid, versao, _ = compra(conn, c.uid, c.cartao, DATA_COMPRA, ent["total"], ent["parcelas"])
    pagar(conn, c, f["entrada"]["pagamentos"][0])
    assert saldo(conn, c.uid, c.cartao, DATA_ESTORNO) == dec(e["saldo_cartao_antes"])
    assert pago_da(conn, c, tid) == dec(e["pago_alocado"])
    antes = foto(conn, c, DATA_ESTORNO)

    r = estornar(conn, c, tid, versao)

    assert r.limite_devolvido == dec(e["limite_devolvido"])
    assert r.credito == dec(e["credito_proxima_fatura_aberta"])
    assert saldo(conn, c.uid, c.cartao, DATA_ESTORNO) == dec(e["saldo_cartao_depois"])
    assert pool(conn, c) == dec(e["pool_restante"])
    assert liquido(conn, c, antes, ent["total"], DATA_ESTORNO) == dec(e["liquido_da_compra"])


# ---------------------------------------------------------------------------------------------
# Propriedades (AC-3 e o pool)
# ---------------------------------------------------------------------------------------------

_CONFIG = settings(
    max_examples=40, deadline=None, suppress_health_check=[HealthCheck.function_scoped_fixture]
)


@_CONFIG
@given(
    total_c=st.integers(min_value=4, max_value=500_000),
    n=st.integers(min_value=1, max_value=4),
    pago_c=st.integers(min_value=0, max_value=1_000_000),
)
def test_liquido_zero(conn: psycopg.Connection, total_c: int, n: int, pago_c: int) -> None:
    """SPEC-006-AC-3: -T + N + P = 0 para qualquer total, parcelas e valor pago."""
    with conn.transaction(force_rollback=True):
        c = montar(conn)
        tid, versao, _ = compra(conn, c.uid, c.cartao, DATA_COMPRA, _reais(total_c), n)
        if pago_c:
            pagar(conn, c, _reais(pago_c))
        antes = foto(conn, c, DATA_ESTORNO)

        r = estornar(conn, c, tid, versao)

        # líquido medido no saldo e no limite usado, não nos campos devolvidos
        assert liquido(conn, c, antes, _reais(total_c), DATA_ESTORNO) == 0
        assert r.total == dec(_reais(total_c))
        # com uma só compra, o crédito é o menor entre o pago e o total
        assert r.credito == dec(_reais(min(total_c, pago_c)))


@_CONFIG
@given(
    totais=st.tuples(
        st.integers(min_value=4, max_value=300_000), st.integers(min_value=4, max_value=300_000)
    ),
    ns=st.tuples(st.integers(min_value=1, max_value=4), st.integers(min_value=1, max_value=4)),
    pago_c=st.integers(min_value=1, max_value=700_000),
    ordem=st.lists(st.sampled_from([0, 1]), unique=True, max_size=2),
)
def test_pool_nunca_negativo(
    conn: psycopg.Connection,
    totais: tuple[int, int],
    ns: tuple[int, int],
    pago_c: int,
    ordem: list[int],
) -> None:
    """O pool de pagamentos não fica negativo após qualquer sequência de estornos."""
    with conn.transaction(force_rollback=True):
        c = montar(conn)
        compras = [
            compra(conn, c.uid, c.cartao, DATA_COMPRA, _reais(totais[i]), ns[i]) for i in range(2)
        ]
        pagar(conn, c, _reais(pago_c))
        creditos = Decimal(0)
        for i in ordem:
            r = estornar(conn, c, compras[i][0], compras[i][1])
            creditos += r.credito
            assert 0 <= r.credito <= r.total
            assert pool(conn, c) >= 0
            assert pool(conn, c) == dec(_reais(pago_c)) - creditos
        if len(ordem) == 2:  # tudo estornado: o crédito total é o menor entre o pago e a dívida
            assert creditos == dec(_reais(min(pago_c, totais[0] + totais[1])))


# ---------------------------------------------------------------------------------------------
# Fechamento, edição bloqueada, compra preservada
# ---------------------------------------------------------------------------------------------


def test_estorno_no_dia_do_fechamento_cai_na_fatura_seguinte(conn: psycopg.Connection) -> None:
    """SPEC-006-AC-6: dia 10 é o fechamento; o crédito de 10/07 vai para 2025-08, o de 09/07 não."""
    esperado = {"2025-07-09": "2025-07", "2025-07-10": "2025-08"}
    for data, competencia in esperado.items():
        c = montar(conn)
        tid, versao, _ = compra(conn, c.uid, c.cartao, DATA_COMPRA, "400.00", 4)
        pagar(conn, c, "100.00")
        r = estornar(conn, c, tid, versao, data)
        assert r.competencia == competencia, data
        assert fatura(conn, c, competencia) == dec("-100.00")

    # o fechamento vigente na data do estorno é o que vale (ADR 043 item 5): dia 20 desde julho
    c = montar(conn)
    fechar(conn, c.uid, c.cartao, 20, "2025-07-01")
    tid, versao, _ = compra(conn, c.uid, c.cartao, DATA_COMPRA, "400.00", 4)
    pagar(conn, c, "100.00")
    assert estornar(conn, c, tid, versao, "2025-07-10").competencia == "2025-07"


def test_f_est_06(conn: psycopg.Connection) -> None:
    """SPEC-006-AC-8: editar ou excluir compra com parte paga é recusado e nada muda."""
    f = fixture("F-EST-06")
    ent, ed, e = f["entrada"]["compra"], f["entrada"]["edicao"], f["esperado"]
    c = montar(conn)
    tid, versao, _ = compra(conn, c.uid, c.cartao, DATA_COMPRA, ent["total"], ent["parcelas"])
    pagar(conn, c, f["entrada"]["pagamentos"][0])
    assert pago_da(conn, c, tid) == dec(e["pago_alocado"])
    parcelas_antes = parcelas_da(conn, c.uid, tid)

    with recusa_com(conn, "AB422", "estorne a compra"):
        compra(
            conn, c.uid, c.cartao, DATA_COMPRA, ed["total"], ed["parcelas"],
            transacao_id=tid, versao=versao,
        )  # fmt: skip

    assert e["edicao_aceita"] is False
    assert parcelas_da(conn, c.uid, tid) == parcelas_antes
    assert sum(dec(v) for v, _ in parcelas_da(conn, c.uid, tid)) == -dec(
        e["compra_vigente"]["total"]
    )
    assert len(parcelas_antes) == e["compra_vigente"]["parcelas"]
    assert saldo(conn, c.uid, c.cartao, DATA_ESTORNO) == dec(e["saldo_cartao"])
    assert usado(conn, c, DATA_ESTORNO) == dec(e["limite_usado"])

    # A exclusão também é recusada (ADR 044 item 8); nada muda.
    with recusa_com(conn, "AB422", "excluída: estorne a compra"):
        excluir(conn, c.uid, tid, versao)
    assert parcelas_da(conn, c.uid, tid) == parcelas_antes

    # Compra sem nada pago continua editável (SPEC-005-AC-10) e excluível.
    outro = montar(conn)
    t2, v2, _ = compra(conn, outro.uid, outro.cartao, DATA_COMPRA, "400.00", 4)
    _, v2b, _ = compra(
        conn, outro.uid, outro.cartao, DATA_COMPRA, "600.00", 4, transacao_id=t2, versao=v2
    )
    assert v2b == v2 + 1
    assert sum(dec(v) for v, _ in parcelas_da(conn, outro.uid, t2)) == dec("-600.00")
    excluir(conn, outro.uid, t2, v2b)
    assert parcelas_da(conn, outro.uid, t2) == []


def test_compra_original_preservada_e_um_estorno_por_compra(conn: psycopg.Connection) -> None:
    """SPEC-006-AC-9: compra intacta, um estorno ligado a ela e gasto fora das competências."""
    c = montar(conn)
    tid, versao, _ = compra(conn, c.uid, c.cartao, DATA_COMPRA, "400.00", 4)
    pagar(conn, c, "100.00")
    competencias = ["2025-03", "2025-04", "2025-05", "2025-06"]

    def gasto_cartao() -> dict[str, Decimal]:
        linhas = conn.execute(
            "SELECT competencia, -sum(valor) FROM parcela_ativa WHERE user_id = %s "
            "GROUP BY competencia ORDER BY competencia",
            (c.uid,),
        ).fetchall()
        return dict(linhas)

    assert gasto_cartao() == {k: dec("100.00") for k in competencias}
    r = estornar(conn, c, tid, versao)

    # as parcelas saem do gasto nas competências originais; o crédito não entra como receita
    assert gasto_cartao() == {}
    assert conn.execute(
        "SELECT count(*) FROM transacao_vigente WHERE user_id = %s AND tipo = 'receita'",
        (c.uid,),
    ).fetchone() == (0,)
    # a compra continua lá, vigente, nas mesmas quatro parcelas (nada de exclusão nem edição)
    original = conn.execute(
        "SELECT versao, vigente, excluida, valor, competencia FROM transacao_versao "
        "WHERE user_id = %s AND transacao_id = %s ORDER BY parcela",
        (c.uid, tid),
    ).fetchall()
    assert original == [(1, True, False, dec("-100.00"), k) for k in competencias]
    # o estorno está ligado a ela, é positivo (+T) e é único
    ligacao = conn.execute(
        "SELECT estorno_de, valor, estorno_credito, tipo FROM transacao_vigente "
        "WHERE user_id = %s AND transacao_id = %s",
        (c.uid, r.id),
    ).fetchall()
    assert ligacao == [(tid, dec("400.00"), dec("100.00"), "estorno")]
    with recusa_com(conn, "AB410", "já foi estornada"):
        estornar(conn, c, tid, versao)
    assert conn.execute(
        "SELECT count(*) FROM transacao_vigente WHERE user_id = %s AND tipo = 'estorno'",
        (c.uid,),
    ).fetchone() == (1,)


def test_estorno_recusas_de_entrada(conn: psycopg.Connection) -> None:
    c = montar(conn)
    tid, versao, _ = compra(conn, c.uid, c.cartao, DATA_COMPRA, "400.00", 4)
    debito = lancar(conn, c.uid, "debito", DATA_COMPRA, c.corrente, "10.00")[0]
    with Recusa(conn, "AB409"):
        estornar(conn, c, tid, versao + 1)  # versão que o cliente não leu
    with Recusa(conn, "AB422"):
        estornar(conn, c, debito)  # só compra a crédito se estorna
    with Recusa(conn, "AB404"):
        estornar(conn, c, tid + 10_000_000)
    with Recusa(conn, "AB422"):
        estornar(conn, c, tid, versao, "2025-03-04")  # antes da compra
    futuro = (date.today() + timedelta(days=366)).isoformat()
    with Recusa(conn, "AB422"):
        estornar(conn, c, tid, versao, futuro)
    # outro usuário não alcança a compra (INV-13): para ele ela não existe
    intruso = montar(conn)
    with Recusa(conn, "AB404"):
        estornar(conn, intruso, tid, versao)
    # nada foi gravado
    assert conn.execute(
        "SELECT count(*) FROM transacao_versao WHERE tipo = 'estorno' AND user_id IN (%s, %s)",
        (c.uid, intruso.uid),
    ).fetchone() == (0,)


def test_depois_do_estorno_pagamento_compra_e_estorno_ficam_imutaveis(
    conn: psycopg.Connection,
) -> None:
    """SPEC-006-AC-10: com estorno no cartão, editar/excluir qualquer lançamento dele é recusado."""
    c = montar(conn)
    ta, va, _ = compra(conn, c.uid, c.cartao, DATA_COMPRA, "400.00", 4)
    tb, vb, _ = compra(conn, c.uid, c.cartao, "2025-03-20", "200.00", 1)
    pg = pagar(conn, c, "150.00")
    r = estornar(conn, c, ta, va)
    assert pool(conn, c) == dec("0.00")

    def contagem() -> int:
        linha = conn.execute(
            "SELECT count(*) FROM transacao_versao WHERE user_id = %s", (c.uid,)
        ).fetchone()
        assert linha is not None
        return int(linha[0])

    antes = contagem()
    with recusa_com(conn, "AB422", "pagamento recebido"):
        lancar(
            conn, c.uid, "transferencia", DATA_PAGAMENTO, c.corrente, "100.00",
            destino=c.cartao, transacao_id=pg, versao=1,
        )  # fmt: skip
    with recusa_com(conn, "AB422", "pagamento recebido"):
        excluir(conn, c.uid, pg, 1)
    with recusa_com(conn, "AB422", "compra foi estornada"):
        compra(conn, c.uid, c.cartao, DATA_COMPRA, "400.00", 4, transacao_id=ta, versao=va)
    with recusa_com(conn, "AB422", "compra foi estornada"):
        excluir(conn, c.uid, ta, va)
    with recusa_com(conn, "AB422", "estorno não pode"):
        lancar(
            conn, c.uid, "debito", DATA_ESTORNO, c.corrente, "10.00", transacao_id=r.id, versao=1
        )
    with recusa_com(conn, "AB422", "estorno não pode"):
        excluir(conn, c.uid, r.id, 1)

    assert contagem() == antes  # nada mudou
    assert pool(conn, c) == dec("0.00")
    assert pool(conn, c) >= 0

    # Qualquer lançamento já gravado no cartão é imutável, mesmo a compra B (nada pago, nada
    # estornada) e o pagamento que ainda não foi tocado (ADR 044 item 9).
    with recusa_com(conn, "AB422", "já gravados nele"):
        compra(conn, c.uid, c.cartao, "2025-03-20", "250.00", 1, transacao_id=tb, versao=vb)
    with recusa_com(conn, "AB422", "já gravados nele"):
        excluir(conn, c.uid, tb, vb)
    assert contagem() == antes

    # Lançamentos NOVOS no cartão continuam aceitos: compra nova e pagamento novo.
    tn, _, _ = compra(conn, c.uid, c.cartao, "2025-04-12", "60.00", 2)
    pagar(conn, c, "10.00")
    assert pool(conn, c) == dec("10.00")
    assert contagem() == antes + 2 + 2  # 2 parcelas + 2 pernas
    assert sum(dec(v) for v, _ in parcelas_da(conn, c.uid, tn)) == dec("-60.00")


def test_faturas_antigas_nao_mudam(conn: psycopg.Connection) -> None:
    """SPEC-006-AC-11: a compra estornada sai só das faturas do crédito em diante (ADR 044 item 10).

    Compra 400 em 4x (2025-03..06), pagamento 100, estorno em 2025-04-20 (crédito em 2025-05).
    """
    c = montar(conn)
    tid, versao, _ = compra(conn, c.uid, c.cartao, DATA_COMPRA, "400.00", 4)
    pagar(conn, c, "100.00")
    antes = {k: fatura(conn, c, k) for k in ("2025-03", "2025-04", "2025-05", "2025-06")}
    assert antes == {k: dec("100.00") for k in antes}
    itens_marco = conn.execute(
        "SELECT transacao_id, parcela, parcelas, valor FROM fatura_itens(%s, %s, '2025-03')",
        (c.uid, c.cartao),
    ).fetchall()

    r = estornar(conn, c, tid, versao)
    assert r.competencia == "2025-05"

    # Anteriores ao crédito: o mesmo valor e a mesma compra (parcela 1 de 4, por exemplo).
    assert fatura(conn, c, "2025-03") == dec("100.00")
    assert fatura(conn, c, "2025-04") == dec("100.00")
    assert (
        conn.execute(
            "SELECT transacao_id, parcela, parcelas, valor FROM fatura_itens(%s, %s, '2025-03')",
            (c.uid, c.cartao),
        ).fetchall()
        == itens_marco
        == [(tid, 1, 4, dec("100.00"))]
    )
    # Da competência do crédito em diante: sem a compra; o crédito P fica na do estorno.
    assert fatura(conn, c, "2025-05") == dec("-100.00")
    assert fatura(conn, c, "2025-06") == dec("0.00")
    # O gasto real (parcela_ativa) segue o ADR 044 item 5, independente da fatura: a compra
    # estornada sai de TODAS as competências originais.
    assert conn.execute(
        "SELECT count(*) FROM parcela_ativa WHERE user_id = %s", (c.uid,)
    ).fetchone() == (0,)


def _com_estorno(conn: psycopg.Connection) -> Cenario:
    """Cartão com uma compra de 400 em 4x, pagamento de 150 e a compra estornada."""
    c = montar(conn)
    tid, versao, _ = compra(conn, c.uid, c.cartao, DATA_COMPRA, "400.00", 4)
    pagar(conn, c, "150.00")
    estornar(conn, c, tid, versao)
    return c


def test_conversao_para_cartao_com_estorno_e_recusada(conn: psycopg.Connection) -> None:
    """Lançamento já gravado não vira compra/pagamento de cartão que tem estorno (ADR 044)."""
    c = _com_estorno(conn)
    outra = conta(conn, c.uid, "outra")
    debito, vd, _ = lancar(conn, c.uid, "debito", "2025-04-01", c.corrente, "30.00")
    transf, vt, _ = lancar(
        conn, c.uid, "transferencia", "2025-04-02", c.corrente, "20.00", destino=outra
    )
    antes = pool(conn, c)

    with recusa_com(conn, "AB422", "só lançamentos novos"):
        compra(conn, c.uid, c.cartao, "2025-04-01", "30.00", 2, transacao_id=debito, versao=vd)
    with recusa_com(conn, "AB422", "só lançamentos novos"):
        lancar(
            conn, c.uid, "transferencia", "2025-04-02", c.corrente, "20.00",
            destino=c.cartao, transacao_id=transf, versao=vt,
        )  # fmt: skip
    assert pool(conn, c) == antes
    # nada mudou: os dois seguem na versão 1
    assert conn.execute(
        "SELECT count(*) FROM transacao_versao WHERE user_id = %s AND transacao_id IN (%s, %s) "
        "AND versao > 1",
        (c.uid, debito, transf),
    ).fetchone() == (0,)

    # Lançamento NOVO no mesmo cartão segue aceito.
    compra(conn, c.uid, c.cartao, "2025-04-03", "50.00", 1)
    pagar(conn, c, "10.00")
    assert pool(conn, c) == antes + dec("10.00")

    # Controle: a mesma conversão para um cartão SEM estorno continua permitida.
    livre = cartao(conn, c.uid, "cartao livre", c.linha, 10, "2000-01-01")
    _, v2, _ = compra(conn, c.uid, livre, "2025-04-01", "30.00", 2, transacao_id=debito, versao=vd)
    assert v2 == vd + 1


def test_conta_do_cartao_com_estorno_nao_muda_de_tipo(conn: psycopg.Connection) -> None:
    """A regra da 0006 (conta com lançamentos não sai do tipo cartão) já protege; não há excluir."""
    c = _com_estorno(conn)
    with recusa_com(conn, "AB422", "tipo cartão"):
        conn.execute(
            "SELECT conta_gravar(%s, %s, 1, 'cartao', 'corrente', NULL)", (c.uid, c.cartao)
        )
    # Nenhuma função exclui conta (conta_gravar sempre grava excluida = false): se um dia
    # existir, este teste obriga a tratar o cartão com estorno.
    funcoes = conn.execute(
        "SELECT proname FROM pg_proc WHERE proname ILIKE '%conta%excluir%' "
        "OR proname ILIKE '%excluir%conta%'"
    ).fetchall()
    assert funcoes == []


def test_leituras_do_estorno_nao_vazam_para_outro_usuario(conn: psycopg.Connection) -> None:
    """Com o user_id de outro usuário, pool, alocação, compra paga e fatura vêm vazios/zero."""
    c = montar(conn)
    tid, versao, _ = compra(conn, c.uid, c.cartao, DATA_COMPRA, "400.00", 4)
    pagar(conn, c, "150.00")
    # sanidade: para o dono há dado
    assert pool(conn, c) == dec("150.00")
    assert fatura(conn, c, "2025-03") == dec("100.00")
    estornar(conn, c, tid, versao)

    intruso = montar(conn)
    xx = Cenario(intruso.uid, intruso.corrente, intruso.linha, c.cartao)  # cartão alheio
    assert pool(conn, xx) == dec("0")
    assert alocado(conn, xx) == []
    assert conn.execute(
        "SELECT count(*) FROM compra_paga(%s, %s)", (intruso.uid, tid)
    ).fetchone() == (0,)
    for competencia in ("2025-03", "2025-05"):
        assert fatura(conn, xx, competencia) == dec("0")
        assert conn.execute(
            "SELECT count(*) FROM fatura_itens(%s, %s, %s)", (intruso.uid, c.cartao, competencia)
        ).fetchone() == (0,)


def _preparar_commitado(url: str) -> tuple[Cenario, int, int]:
    with psycopg.connect(url) as prep:
        c = montar(prep)
        tid, versao, _ = compra(prep, c.uid, c.cartao, DATA_COMPRA, "400.00", 4)
        prep.commit()
    return c, tid, versao


def test_corrida_pagamento_novo_antes_da_edicao_recusa_a_edicao(esquema: str) -> None:
    """O pagamento (criação) toma a trava do cartão: a edição espera e então vê a parte paga."""
    c, tid, versao = _preparar_commitado(esquema)
    try:
        _, edicao = corrida(
            esquema,
            lambda a: pagar(a, c, "150.00"),
            lambda b: compra(
                b, c.uid, c.cartao, DATA_COMPRA, "600.00", 4, transacao_id=tid, versao=versao
            ),
        )
        assert edicao == "AB422"
        with psycopg.connect(esquema) as ver:
            soma = ver.execute(
                "SELECT sum(valor) FROM transacao_vigente WHERE user_id = %s AND transacao_id = %s",
                (c.uid, tid),
            ).fetchone()
            assert soma == (dec("-400.00"),)  # a compra com parte paga não foi alterada
    finally:
        apagar_usuario(esquema, c.uid)


def test_corrida_edicao_antes_do_pagamento_novo_serializa(esquema: str) -> None:
    """A edição segura a trava; o pagamento novo espera e entra depois, sobre a compra editada."""
    c, tid, versao = _preparar_commitado(esquema)
    try:
        edicao, pagamento = corrida(
            esquema,
            lambda a: compra(
                a, c.uid, c.cartao, DATA_COMPRA, "600.00", 4, transacao_id=tid, versao=versao
            ),
            lambda b: pagar(b, c, "150.00"),
        )
        assert isinstance(edicao, tuple) and isinstance(pagamento, int)  # nenhuma recusa
        with psycopg.connect(esquema) as ver:
            soma = ver.execute(
                "SELECT sum(valor) FROM transacao_vigente WHERE user_id = %s AND transacao_id = %s",
                (c.uid, tid),
            ).fetchone()
            assert soma == (dec("-600.00"),)
            assert pool(ver, c) == dec("150.00")
    finally:
        apagar_usuario(esquema, c.uid)
