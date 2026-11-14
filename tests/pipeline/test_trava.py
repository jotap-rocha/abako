"""SPEC-014-AC-3 (INV-35): execuções simultâneas são impedidas; a segunda não toca o arquivo."""

from __future__ import annotations

import threading
from collections.abc import Callable
from pathlib import Path
from typing import Any

import psycopg
import pytest

from pipeline import executar as modulo
from pipeline.config import Config
from pipeline.executar import SUCESSO, TRAVA_CLASSE, TRAVA_OBJETO, TRAVADO, executar
from tests.pipeline.util_pipeline import Cenario, sha

pytestmark = pytest.mark.banco


def _listagem(pasta: Path) -> dict[str, tuple[int, int]]:
    return {p.name: (p.stat().st_size, p.stat().st_mtime_ns) for p in sorted(pasta.iterdir())}


def test_execucao_simultanea(
    fazer_config: Callable[..., Config], cenario: Cenario, monkeypatch: pytest.MonkeyPatch
) -> None:
    config = fazer_config()
    assert executar(config) == SUCESSO
    hash_anterior = sha(config.arquivo)
    pasta_antes = _listagem(config.diretorio)

    original = modulo.construir
    dentro = threading.Event()
    liberar = threading.Event()

    def segurar(*args: Any, **kwargs: Any) -> dict[str, int]:
        dentro.set()  # a primeira execução já tem a trava e ainda não gerou nada
        assert liberar.wait(timeout=30)
        return original(*args, **kwargs)

    monkeypatch.setattr(modulo, "construir", segurar)
    resultado: list[int] = []
    primeira = threading.Thread(target=lambda: resultado.append(executar(config)))
    primeira.start()
    try:
        assert dentro.wait(timeout=30)
        # a segunda, enquanto a primeira segura a trava: falha rápido e não toca em nada
        assert executar(config) == TRAVADO
        assert sha(config.arquivo) == hash_anterior
        assert _listagem(config.diretorio) == pasta_antes
    finally:
        liberar.set()
        primeira.join(timeout=60)
    assert resultado == [SUCESSO]
    # a trava foi solta: uma nova execução volta a funcionar
    monkeypatch.setattr(modulo, "construir", original)
    assert executar(config) == SUCESSO


def test_trava_externa_impede_sem_criar_nada(
    fazer_config: Callable[..., Config], cenario: Cenario, url_pipeline: str
) -> None:
    """Trava tomada por outra sessão (outro processo): nem a pasta do arquivo é criada."""
    config = fazer_config()
    assert not config.diretorio.exists()  # pasta inexistente de partida
    with psycopg.connect(url_pipeline, autocommit=True) as outro:
        linha = outro.execute(
            "SELECT pg_try_advisory_lock(%s, %s)", (TRAVA_CLASSE, TRAVA_OBJETO)
        ).fetchone()
        assert linha == (True,)
        try:
            assert executar(config) == TRAVADO
        finally:
            outro.execute("SELECT pg_advisory_unlock(%s, %s)", (TRAVA_CLASSE, TRAVA_OBJETO))
    assert not config.diretorio.exists()  # nem a pasta foi criada
    assert not config.arquivo.exists()
    assert executar(config) == SUCESSO
