"""SPEC-014-AC-4: falha no meio mantém o arquivo anterior e não deixa temporário."""

from __future__ import annotations

import os
from collections.abc import Callable
from typing import Any

import pytest

from pipeline import esquema, extracao
from pipeline import executar as modulo
from pipeline.config import Config
from pipeline.executar import FALHA, SUCESSO, ValidacaoFalhou, executar
from tests.pipeline.util_pipeline import Cenario, sha, tabelas_do_arquivo

pytestmark = pytest.mark.banco


def _explode(*_: Any, **__: Any) -> Any:
    raise RuntimeError("falha injetada")


def _validacao(*_: Any, **__: Any) -> None:
    raise ValidacaoFalhou("falha injetada")


# (módulo, atributo, substituto): leitura, meio da escrita e validação do arquivo novo
PONTOS = [
    pytest.param(extracao, "fatura_resumo", _explode, id="leitura"),
    pytest.param(esquema, "inserir", _explode, id="escrita"),
    pytest.param(modulo, "validar", _validacao, id="validacao"),
]


@pytest.mark.parametrize(("alvo", "atributo", "falha"), PONTOS)
def test_falha_mantem_anterior(
    fazer_config: Callable[..., Config],
    cenario: Cenario,
    monkeypatch: pytest.MonkeyPatch,
    alvo: Any,
    atributo: str,
    falha: Callable[..., Any],
) -> None:
    config = fazer_config()
    assert executar(config) == SUCESSO
    hash_anterior = sha(config.arquivo)
    conteudo_anterior = tabelas_do_arquivo(config.arquivo)

    monkeypatch.setattr(alvo, atributo, falha)
    assert executar(config) == FALHA
    monkeypatch.undo()

    assert sha(config.arquivo) == hash_anterior  # o anterior segue intacto
    assert tabelas_do_arquivo(config.arquivo) == conteudo_anterior
    assert sorted(p.name for p in config.diretorio.iterdir()) == [config.arquivo.name]  # sem .tmp
    # e o pipeline continua utilizável depois da falha (a trava foi solta)
    assert executar(config) == SUCESSO


def test_falha_na_primeira_execucao_nao_cria_arquivo(
    fazer_config: Callable[..., Config], cenario: Cenario, monkeypatch: pytest.MonkeyPatch
) -> None:
    config = fazer_config()
    monkeypatch.setattr(modulo, "validar", _validacao)
    assert executar(config) == FALHA
    assert list(config.diretorio.iterdir()) == []  # nem arquivo parcial nem .tmp


def test_restos_de_execucao_morta_sao_limpos(
    fazer_config: Callable[..., Config], cenario: Cenario
) -> None:
    config = fazer_config()
    config.diretorio.mkdir(parents=True)
    (config.diretorio / f"{config.arquivo.name}.deadbeef.tmp").write_bytes(b"resto")
    assert executar(config) == SUCESSO
    assert sorted(p.name for p in config.diretorio.iterdir()) == [config.arquivo.name]


def test_troca_recusada_pelo_sistema_mantem_anterior(
    fazer_config: Callable[..., Config], cenario: Cenario, monkeypatch: pytest.MonkeyPatch
) -> None:
    """No Windows o os.replace falha com PermissionError se um leitor mantém o arquivo aberto:
    o código é 4, o anterior segue íntegro e o temporário é apagado."""
    config = fazer_config()
    assert executar(config) == SUCESSO
    hash_anterior = sha(config.arquivo)

    def recusa(*_: Any, **__: Any) -> None:
        raise PermissionError("arquivo em uso")

    monkeypatch.setattr(os, "replace", recusa)
    assert executar(config) == FALHA
    monkeypatch.undo()

    assert sha(config.arquivo) == hash_anterior
    assert sorted(p.name for p in config.diretorio.iterdir()) == [config.arquivo.name]
    assert executar(config) == SUCESSO
