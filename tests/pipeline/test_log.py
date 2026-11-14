"""SPEC-014-AC-7: o log não leva dado financeiro, nome nem descrição (R4 só contagem)."""

from __future__ import annotations

import logging
from collections.abc import Callable
from typing import Any

import pytest

from pipeline import extracao
from pipeline.config import Config
from pipeline.executar import FALHA, SUCESSO, executar
from tests.pipeline.util_pipeline import Cenario

pytestmark = pytest.mark.banco

# Valores da F-PIPE-01 que aparecem nos agregados e nunca podem aparecer em log.
VALORES = ("1130.00", "2010.00", "3000.00", "990.00", "340.00", "660.00", "190.00", "60.00", "1250")


def _texto(caplog: pytest.LogCaptureFixture) -> str:
    return "\n".join(r.getMessage() for r in caplog.records)


def test_log_sem_dado_financeiro_nem_nome(
    fazer_config: Callable[..., Config],
    cenario: Cenario,
    caplog: pytest.LogCaptureFixture,
    capsys: pytest.CaptureFixture[str],
) -> None:
    config = fazer_config()
    with caplog.at_level(logging.DEBUG):
        assert executar(config) == SUCESSO
    texto = _texto(caplog)
    for etapa in ("leitura", "escrita", "validacao", "troca"):
        assert f"etapa={etapa} " in texto
    assert "registros_lidos=" in texto and "duracao_ms=" in texto and "run_id=" in texto
    assert "R4: divergencias=1" in texto  # só a contagem da divergência da F-PIPE-01
    assert "MARC" not in texto
    for valor in VALORES:
        assert valor not in texto
    for uid in (cenario.a.uid, cenario.b.uid):
        assert f"user_id={uid}" not in texto
    saida = capsys.readouterr()
    assert saida.out == "" and "MARC" not in saida.err


def test_log_de_falha_nao_repete_a_mensagem_do_erro(
    fazer_config: Callable[..., Config],
    cenario: Cenario,
    caplog: pytest.LogCaptureFixture,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def explode(*_: Any, **__: Any) -> Any:
        raise RuntimeError("MARC_SEGREDO 999.99 conta de fulano")

    monkeypatch.setattr(extracao, "gasto_mensal", explode)
    with caplog.at_level(logging.DEBUG):
        assert executar(fazer_config()) == FALHA
    texto = _texto(caplog)
    assert "erro=RuntimeError" in texto
    assert "MARC" not in texto and "999.99" not in texto and "fulano" not in texto
    assert all(r.exc_info is None for r in caplog.records)  # sem traceback com parâmetros
