"""ABAKO_ENV escolhe o banco do servidor sem segredo novo: só o nome do banco troca."""

from __future__ import annotations

import pytest
from pydantic import SecretStr

from backend.settings import Settings

URL_TST = "postgresql://abako_app:senha-de-teste@127.0.0.1:5433/tst"


def test_tst_e_o_padrao_e_nao_muda_a_url() -> None:
    cfg = Settings(db_app_url=SecretStr(URL_TST))
    assert cfg.env == "tst"
    assert cfg.url_banco == URL_TST


def test_prd_troca_so_o_nome_do_banco() -> None:
    cfg = Settings(db_app_url=SecretStr(URL_TST), env="prd")
    assert cfg.url_banco == "postgresql://abako_app:senha-de-teste@127.0.0.1:5433/prd"


def test_prd_recusa_url_que_nao_aponta_para_tst() -> None:
    cfg = Settings(db_app_url=SecretStr(URL_TST.replace("/tst", "/outro")), env="prd")
    with pytest.raises(ValueError):
        _ = cfg.url_banco


def test_env_invalido_e_recusado() -> None:
    with pytest.raises(ValueError):
        Settings(db_app_url=SecretStr(URL_TST), env="dev")  # type: ignore[arg-type]
