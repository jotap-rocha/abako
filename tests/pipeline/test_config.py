"""SPEC-014-AC-10: alvo e pasta do analítico passam por guardas antes de qualquer conexão."""

from __future__ import annotations

from datetime import date
from pathlib import Path

import pytest

from db.alvo import RAIZ
from pipeline.config import ConfigInvalida, caminho_arquivo, montar

URL_TST = "postgresql://abako_pipeline:x@127.0.0.1:5433/tst"
URL_PRD = "postgresql://abako_pipeline:x@127.0.0.1:5433/prd"
HOJE = date(2026, 2, 20)


def test_alvo_tst_valido_e_pasta_externa(tmp_path: Path) -> None:
    env = {"ABAKO_DB_PIPELINE_URL": URL_TST, "ABAKO_ANALITICO_DIR": str(tmp_path)}
    cfg = montar(env, "tst", hoje=HOJE)
    assert cfg.arquivo == tmp_path.resolve() / "analitico_tst.duckdb"
    assert cfg.hoje == HOJE


@pytest.mark.parametrize(
    "env",
    [
        {},  # sem URL
        {"ABAKO_DB_PIPELINE_URL": "postgresql://abako_owner_tst:x@127.0.0.1:5433/tst"},  # dono
        {"ABAKO_DB_PIPELINE_URL": "postgresql://abako_pipeline:x@127.0.0.1:5432/tst"},  # porta
        {"ABAKO_DB_PIPELINE_URL": "postgresql://abako_pipeline:x@127.0.0.1:5433/prd"},  # banco
        {"ABAKO_DB_PIPELINE_URL": "postgresql://abako_pipeline:x@db.exemplo.com:5433/tst"},
    ],
)
def test_url_fora_do_guarda_e_recusada(env: dict[str, str], tmp_path: Path) -> None:
    with pytest.raises(ConfigInvalida):
        montar({**env, "ABAKO_ANALITICO_DIR": str(tmp_path)}, "tst")


def test_prd_exige_confirmacao_humana(tmp_path: Path) -> None:
    env = {"ABAKO_DB_PIPELINE_URL_PRD": URL_PRD, "ABAKO_ANALITICO_DIR": str(tmp_path)}
    with pytest.raises(ConfigInvalida):
        montar(env, "prd")
    with pytest.raises(ConfigInvalida):
        montar({**env, "ABAKO_CONFIRMA_PRD": "talvez"}, "prd")
    cfg = montar({**env, "ABAKO_CONFIRMA_PRD": "sim"}, "prd", hoje=HOJE)
    assert cfg.arquivo.name == "analitico_prd.duckdb"  # arquivo próprio: nunca o do tst


def test_pasta_dentro_do_repositorio_e_recusada() -> None:
    env = {"ABAKO_DB_PIPELINE_URL": URL_TST, "ABAKO_ANALITICO_DIR": str(RAIZ / "data")}
    with pytest.raises(ConfigInvalida):
        montar(env, "tst")
    with pytest.raises(ConfigInvalida):
        caminho_arquivo({}, "tst", RAIZ)
    with pytest.raises(ConfigInvalida):
        caminho_arquivo({}, "xpto", RAIZ.parent)


def test_pasta_padrao_fica_fora_do_repositorio() -> None:
    caminho = caminho_arquivo({}, "tst")
    assert RAIZ not in caminho.parents


def test_url_malformada_vira_config_invalida_sem_vazar_a_url(tmp_path: Path) -> None:
    env = {
        "ABAKO_DB_PIPELINE_URL": "postgresql://abako_pipeline:SenhaSecreta@[::1:5433/tst",
        "ABAKO_ANALITICO_DIR": str(tmp_path),
    }
    with pytest.raises(ConfigInvalida) as info:
        montar(env, "tst")
    assert "SenhaSecreta" not in str(info.value)
    assert info.value.__cause__ is None and info.value.__suppress_context__
