"""SPEC-013 / INV-21 e INV-25: propriedades do vale com Hypothesis.

O oráculo é aritmética inteira em centavos escrita no teste (min, max, soma), não a fórmula do SQL;
cada exemplo monta um usuário novo (tudo é desfeito no rollback da conexão do teste).
"""

from __future__ import annotations

from decimal import Decimal

import psycopg
import pytest
from hypothesis import HealthCheck, given, settings
from hypothesis import strategies as st

from tests.db.util_vale import HOJE, decidir, mes_do_vale, novo_vale, saldo_derivado, situacao

pytestmark = pytest.mark.banco

CONFIG = settings(
    max_examples=25, deadline=None, suppress_health_check=[HealthCheck.function_scoped_fixture]
)
CENTAVOS = st.integers(min_value=0, max_value=300_000)
BASE = st.integers(min_value=0, max_value=60_000)
DESTINO = st.sampled_from(["trabalho", "pessoal", "nenhum"])


def _c(c: int) -> Decimal:
    return Decimal(c).scaleb(-2)


def _txt(c: int) -> str:
    return f"{_c(c):.2f}"


def _esperado(cred: int, base: int, t: int, p: int) -> tuple[int, int, int, int, int]:
    """(inicial T, inicial P, resta T, resta P, sobra) em centavos, ajuste zero."""
    ini_t, ini_p = min(base, cred), max(cred - base, 0)
    rt, rp = ini_t - t, ini_p - p
    return ini_t, ini_p, rt, rp, max(rt, 0) + max(rp, 0)


@CONFIG
@given(cred=CENTAVOS, base=BASE, t=CENTAVOS, p=CENTAVOS)
def test_sobra_por_bolso_sem_compensacao(
    conn: psycopg.Connection, cred: int, base: int, t: int, p: int
) -> None:
    v = novo_vale(conn, base=_txt(base))
    mes_do_vale(conn, v, "2025-01", _txt(cred), _txt(t), _txt(p))
    s = situacao(conn, v.uid, "2025-01")
    ini_t, ini_p, rt, rp, sobra = _esperado(cred, base, t, p)
    assert (s["resta_trabalho"], s["resta_pessoal"]) == (_c(rt), _c(rp))
    assert s["sobra"] == _c(sobra)
    assert s["sobra"] >= 0
    # estouro de um bolso não reduz a sobra do outro
    if rt < 0:
        assert s["sobra"] == _c(max(rp, 0))
    if rp < 0:
        assert s["sobra"] == _c(max(rt, 0))
    if rt < 0 and rp < 0:
        assert s["sobra"] == Decimal("0.00")
    # resta = alocação efetiva − consumo (sem ajuste neste mês)
    assert s["alocacao_trabalho"] - s["consumo_trabalho"] == s["resta_trabalho"]
    assert s["alocacao_pessoal"] - s["consumo_pessoal"] == s["resta_pessoal"]
    assert (s["inicial_trabalho"], s["inicial_pessoal"]) == (_c(ini_t), _c(ini_p))


@CONFIG
@given(cred=CENTAVOS, base=BASE)
def test_alocacao_inicial_min_max(conn: psycopg.Connection, cred: int, base: int) -> None:
    v = novo_vale(conn, base=_txt(base))
    mes_do_vale(conn, v, "2025-01", _txt(cred))
    s = situacao(conn, v.uid, "2025-01")
    assert s["estado"] == ("sem_credito" if cred == 0 else "ok")
    assert s["inicial_trabalho"] == _c(min(base, cred))
    assert s["inicial_pessoal"] == _c(max(cred - base, 0))
    assert s["inicial_trabalho"] + s["inicial_pessoal"] == _c(cred)  # nada se perde nem se cria
    assert s["inicial_trabalho"] >= 0 and s["inicial_pessoal"] >= 0
    if cred <= base:
        assert s["inicial_pessoal"] == Decimal("0.00")


@CONFIG
@given(
    cred1=CENTAVOS,
    t1=CENTAVOS,
    p1=CENTAVOS,
    cred2=CENTAVOS,
    base=BASE,
    decidir_nenhum=st.booleans(),
)
def test_nao_acumula_sem_decisao(
    conn: psycopg.Connection,
    cred1: int,
    t1: int,
    p1: int,
    cred2: int,
    base: int,
    decidir_nenhum: bool,
) -> None:
    """O resto do mês 1 não chega ao mês 2 sem decisão (ou com `nenhum`)."""
    v = novo_vale(conn, base=_txt(base))
    mes_do_vale(conn, v, "2025-01", _txt(cred1), _txt(t1), _txt(p1))
    mes_do_vale(conn, v, "2025-02", _txt(cred2))
    if decidir_nenhum:
        decidir(conn, v.uid, "2025-01", "nenhum")
    s = situacao(conn, v.uid, "2025-02")
    assert (s["ajuste_trabalho"], s["ajuste_pessoal"]) == (Decimal("0.00"), Decimal("0.00"))
    assert (s["alocacao_trabalho"], s["alocacao_pessoal"]) == (
        _c(min(base, cred2)),
        _c(max(cred2 - base, 0)),
    )


@CONFIG
@given(cred1=CENTAVOS, t1=CENTAVOS, p1=CENTAVOS, cred2=CENTAVOS, base=BASE, destino=DESTINO)
def test_decisao_nao_move_saldo(
    conn: psycopg.Connection,
    cred1: int,
    t1: int,
    p1: int,
    cred2: int,
    base: int,
    destino: str,
) -> None:
    """A decisão soma a sobra inteira no destino do mês seguinte e não altera o saldo."""
    v = novo_vale(conn, base=_txt(base))
    mes_do_vale(conn, v, "2025-01", _txt(cred1), _txt(t1), _txt(p1))
    mes_do_vale(conn, v, "2025-02", _txt(cred2))
    antes = saldo_derivado(conn, v.uid, v.vr, HOJE)
    sem = situacao(conn, v.uid, "2025-02")
    decidir(conn, v.uid, "2025-01", destino)
    depois = saldo_derivado(conn, v.uid, v.vr, HOJE)
    assert depois == antes
    com = situacao(conn, v.uid, "2025-02")
    sobra = _c(_esperado(cred1, base, t1, p1)[4])
    adicional_t = sobra if destino == "trabalho" else Decimal("0.00")
    adicional_p = sobra if destino == "pessoal" else Decimal("0.00")
    assert com["alocacao_trabalho"] == sem["alocacao_trabalho"] + adicional_t
    assert com["alocacao_pessoal"] == sem["alocacao_pessoal"] + adicional_p
    # o mês 1 continua com os mesmos números: a decisão não o reescreve
    assert situacao(conn, v.uid, "2025-01")["sobra"] == sobra
