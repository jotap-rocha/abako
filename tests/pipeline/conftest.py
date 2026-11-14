"""Fixtures do pipeline: `tst` real, papel `abako_pipeline` real, cenário commitado e limpo."""

from __future__ import annotations

from collections.abc import Callable, Iterator
from pathlib import Path

import pytest

from pipeline.config import Config
from tests.db.conftest import esquema, url_pipeline, url_tst  # noqa: F401
from tests.pipeline.util_pipeline import HOJE, Cenario, apagar, montar


@pytest.fixture
def cenario(esquema: str) -> Iterator[Cenario]:  # noqa: F811
    c = montar(esquema)
    try:
        yield c
    finally:
        apagar(esquema, c)


@pytest.fixture
def fazer_config(
    url_pipeline: str,  # noqa: F811
    cenario: Cenario,
    tmp_path: Path,
) -> Callable[..., Config]:
    """Config só com os usuários do cenário, numa pasta temporária fora do repositório."""

    def _fazer(usuarios: tuple[int, ...] | None = None) -> Config:
        return Config(
            ambiente="tst",
            url=url_pipeline,
            diretorio=tmp_path / "analitico",
            hoje=HOJE,
            usuarios=usuarios if usuarios is not None else (cenario.a.uid, cenario.b.uid),
        )

    return _fazer
