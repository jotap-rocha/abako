"""SPEC-014-AC-9: a leitura do analítico é somente leitura e sempre filtra por user_id."""

from __future__ import annotations

import json
from collections.abc import Callable
from pathlib import Path

import duckdb
import pytest

from pipeline import ler
from pipeline.config import Config
from pipeline.executar import SUCESSO, executar
from tests.pipeline.util_pipeline import Cenario, sha

pytestmark = pytest.mark.banco


def test_leitura_somente_leitura(
    fazer_config: Callable[..., Config], cenario: Cenario, capsys: pytest.CaptureFixture[str]
) -> None:
    config = fazer_config()
    assert executar(config) == SUCESSO
    antes = sha(config.arquivo)

    linhas = ler.consultar(config.arquivo, "a_receber", cenario.a.uid)
    assert [str(x["total_a_receber"]) for x in linhas] == ["60.00"]
    with pytest.raises(ValueError):
        ler.consultar(config.arquivo, "execucao; DROP TABLE a_receber", cenario.a.uid)

    # a conexão de leitura recusa qualquer escrita
    con = duckdb.connect(str(config.arquivo), read_only=True)
    try:
        for comando in (
            "INSERT INTO a_receber VALUES (1, 1.00)",
            "DELETE FROM saldo_diario",
            "DROP TABLE gasto_mensal",
            "CREATE TABLE intruso (x INT)",
        ):
            with pytest.raises(duckdb.Error):
                con.execute(comando)
    finally:
        con.close()

    # CLI: JSON por linha, só do usuário pedido; nada é alterado
    codigo = ler.main(
        ["a_receber", "--usuario", str(cenario.a.uid), "--destino", str(config.diretorio)]
    )
    assert codigo == 0
    saida = [json.loads(x) for x in capsys.readouterr().out.splitlines()]
    assert saida == [{"user_id": str(cenario.a.uid), "total_a_receber": "60.00"}]
    assert sha(config.arquivo) == antes
    assert sorted(p.name for p in config.diretorio.iterdir()) == [config.arquivo.name]


def test_leitura_sem_arquivo_falha_sem_criar(tmp_path: Path) -> None:
    destino = tmp_path / "vazio"
    assert ler.main(["a_receber", "--usuario", "1", "--destino", str(destino)]) == 4
    assert not destino.exists()
