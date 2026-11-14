"""SPEC-014-AC-2: reexecutar produz agregados idênticos e a soma bate com o transacional."""

from __future__ import annotations

from collections.abc import Callable
from decimal import Decimal

import psycopg
import pytest

from pipeline.config import Config
from pipeline.executar import SUCESSO, executar
from tests.pipeline.util_pipeline import HOJE, Cenario, tabelas_do_arquivo

pytestmark = pytest.mark.banco

SALDO_ORACULO = (
    "WITH s AS (SELECT data_snapshot, valor FROM snapshot_saldo "
    "           WHERE user_id = %s AND conta_id = %s AND data_snapshot <= %s "
    "           ORDER BY data_snapshot DESC, id DESC LIMIT 1) "
    "SELECT COALESCE((SELECT valor FROM s), 0) + COALESCE((SELECT sum(valor) "
    "  FROM transacao_versao WHERE user_id = %s AND conta_id = %s AND vigente "
    "  AND NOT excluida AND data_transacao <= %s "
    "  AND data_transacao > COALESCE((SELECT data_snapshot FROM s), DATE '1900-01-01')), 0)"
)


def test_reexecucao_identica(
    fazer_config: Callable[..., Config], cenario: Cenario, esquema: str
) -> None:
    config = fazer_config()
    assert executar(config) == SUCESSO
    primeira = tabelas_do_arquivo(config.arquivo)
    assert executar(config) == SUCESSO
    segunda = tabelas_do_arquivo(config.arquivo)
    assert segunda == primeira
    assert primeira["saldo_diario"]  # a comparação não é vazia

    # A soma bate com o transacional, conferida direto nas tabelas-base pelo dono (sem usar as
    # funções do pipeline): saldo do último dia = último snapshot + lançamentos posteriores.
    finais = {
        (uid, conta_id): Decimal(saldo)
        for uid, conta_id, data, saldo in primeira["saldo_diario"]
        if data == HOJE
    }
    assert len(finais) == 4  # corrente, reserva e cartão (A) e corrente (B)
    with psycopg.connect(esquema) as c:
        for (uid, conta_id), saldo in finais.items():
            linha = c.execute(SALDO_ORACULO, (uid, conta_id, HOJE, uid, conta_id, HOJE)).fetchone()
            assert linha is not None and linha[0] == saldo
        # gasto: débitos próprios + parcelas próprias (SQL cru nas tabelas-base)
        gasto = c.execute(
            "SELECT COALESCE(sum(-valor), 0) FROM transacao_versao WHERE user_id = %s "
            "AND vigente AND NOT excluida AND tipo IN ('debito', 'credito') "
            "AND pessoa_id IS NULL",
            (cenario.a.uid,),
        ).fetchone()
        c.rollback()
    assert gasto is not None
    soma_gasto = sum(
        (Decimal(r[3]) for r in primeira["gasto_mensal"] if r[0] == cenario.a.uid), Decimal(0)
    )
    assert soma_gasto == gasto[0] == Decimal("600.00")  # 200 + 100 + 3 x 100
