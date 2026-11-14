"""SPEC-014-AC-5/6: agregados batem com F-PIPE-01/02 (à mão) e o analítico é por user_id."""

from __future__ import annotations

from collections.abc import Callable
from datetime import date
from decimal import Decimal
from typing import Any

import pytest

from pipeline import ler
from pipeline.config import Config
from pipeline.executar import SUCESSO, executar
from tests.pipeline.util_pipeline import Cenario, dias_esperados, esperado, tabelas_do_arquivo

pytestmark = pytest.mark.banco


def _linhas(
    conteudo: dict[str, list[tuple[Any, ...]]], tabela: str, uid: int
) -> list[tuple[Any, ...]]:
    return [r[1:] for r in conteudo[tabela] if r[0] == uid]


def _saldos(linhas: list[tuple[Any, ...]], conta: int) -> list[tuple[date, Decimal]]:
    return [(r[1], Decimal(r[2])) for r in linhas if r[0] == conta]


def test_f_pipe_01_valores_da_fixture(
    fazer_config: Callable[..., Config], cenario: Cenario
) -> None:
    e = esperado("F-PIPE-01")
    config = fazer_config()
    assert executar(config) == SUCESSO
    tudo = tabelas_do_arquivo(config.arquivo)
    a = cenario.a
    assert a.reserva is not None and a.cartao is not None
    nomes: dict[str, int] = {
        "corrente": a.corrente,
        "reserva": a.reserva,
        "cartao": a.cartao,
    }

    saldo = _linhas(tudo, "saldo_diario", a.uid)
    for nome, esperado_conta in e["saldo_diario"].items():
        dias = dias_esperados(esperado_conta["trechos"])
        assert len(dias) == esperado_conta["dias"]
        assert _saldos(saldo, nomes[nome]) == dias, nome
    assert len(saldo) == 51 + 37 + 32

    gasto = {(r[0], r[1]): Decimal(r[2]) for r in _linhas(tudo, "gasto_mensal", a.uid)}
    assert gasto == {(g["mes"], nomes[g["conta"]]): Decimal(g["gasto"]) for g in e["gasto_mensal"]}

    faturas = {r[1]: r[2:] for r in _linhas(tudo, "fatura_resumo", a.uid)}
    assert set(faturas) == {f["competencia"] for f in e["fatura_resumo"]}
    for f in e["fatura_resumo"]:
        assert faturas[f["competencia"]] == (
            Decimal(f["total"]),
            Decimal(f["propria"]),
            Decimal(f["terceiros"]),
        )

    limite = e["limite_linha"]
    assert _linhas(tudo, "limite_linha", a.uid) == [
        (
            a.linha,
            Decimal(limite["limite"]),
            Decimal(limite["usado"]),
            Decimal(limite["disponivel"]),
        )
    ]

    (reserva,) = _linhas(tudo, "cobertura_reserva", a.uid)
    r = e["cobertura_reserva"]
    assert reserva == (
        r["contas_reserva"],
        Decimal(r["saldo_liquido"]),
        Decimal(r["imposto_acumulado"]),
        Decimal(r["saldo_bruto"]),
        r["meses_meta"],
        Decimal(r["gasto_essencial"]),
        Decimal(r["meta"]),
        r["nivel"],
        Decimal(r["falta"]),
        Decimal(r["cobertura_meses"]),
        None,  # sem data alvo
        None,
        False,
        None,
        r["config_pendente"],
    )
    assert _linhas(tudo, "a_receber", a.uid) == [(Decimal(e["a_receber"]["total_a_receber"]),)]
    assert tudo["execucao"] == [(date(2026, 2, 20), 1, "tst")]


def test_f_pipe_02_isolamento_por_user_id(
    fazer_config: Callable[..., Config], cenario: Cenario
) -> None:
    """INV-13: cada linha carrega o user_id do dono; um usuário não vê as contas do outro."""
    e = esperado("F-PIPE-02")
    config = fazer_config()
    assert executar(config) == SUCESSO
    tudo = tabelas_do_arquivo(config.arquivo)
    a, b = cenario.a, cenario.b

    saldo_b = _linhas(tudo, "saldo_diario", b.uid)
    assert _saldos(saldo_b, b.corrente) == dias_esperados(e["saldo_diario"]["corrente"]["trechos"])
    assert {r[0] for r in saldo_b} == {b.corrente}
    assert _linhas(tudo, "gasto_mensal", b.uid) == [("2026-01", b.corrente, Decimal("77.00"))]
    assert _linhas(tudo, "fatura_resumo", b.uid) == []
    assert _linhas(tudo, "limite_linha", b.uid) == []
    assert _linhas(tudo, "a_receber", b.uid) == [(Decimal("0.00"),)]
    (reserva_b,) = _linhas(tudo, "cobertura_reserva", b.uid)
    assert reserva_b[0] == 0 and reserva_b[1] == Decimal("0.00") and reserva_b[-1] is True

    # nada de A em B e vice-versa: as contas de cada um só aparecem nas linhas dele
    contas_a = {a.corrente, a.reserva, a.cartao}
    for tabela in ("saldo_diario", "gasto_mensal", "fatura_resumo"):
        for linha in tudo[tabela]:
            uid, conta = linha[0], linha[1] if tabela != "gasto_mensal" else linha[2]
            assert (conta in contas_a) == (uid == a.uid), tabela

    # a leitura filtra pelo user_id recebido (o da sessão) e nunca devolve o de outro
    for uid, outro in ((a.uid, b.uid), (b.uid, a.uid)):
        for tabela in ler.LEGIVEIS:
            linhas = ler.consultar(config.arquivo, tabela, uid)
            assert {x["user_id"] for x in linhas} <= {uid}
            assert outro not in {x["user_id"] for x in linhas}


def test_so_os_usuarios_pedidos_entram_no_arquivo(
    fazer_config: Callable[..., Config], cenario: Cenario
) -> None:
    config = fazer_config((cenario.b.uid,))
    assert executar(config) == SUCESSO
    tudo = tabelas_do_arquivo(config.arquivo)
    ids = {r[0] for t in ler.LEGIVEIS for r in tudo[t]}
    assert ids == {cenario.b.uid}
