"""ADR 042: a 0005 é irreversível com dados; o downgrade se recusa em vez de apagar pernas."""

from __future__ import annotations

from pathlib import Path

import psycopg
import pytest
from alembic import command
from alembic.config import Config

from tests.db.util_lancamento import apagar_usuario, conta, lancar
from tests.db.util_saldo import novo_usuario

pytestmark = pytest.mark.banco

RAIZ = Path(__file__).resolve().parents[2]


def _revisao(url: str) -> str:
    with psycopg.connect(url) as conn:
        linha = conn.execute("SELECT version_num FROM alembic_version").fetchone()
    assert linha is not None
    return str(linha[0])


def test_downgrade_com_transferencia_e_recusado(esquema: str) -> None:
    with psycopg.connect(esquema) as prep:
        uid = novo_usuario(prep)
        a = conta(prep, uid, "a")
        b = conta(prep, uid, "b")
        lancar(prep, uid, "transferencia", "2026-02-05", a, "10.00", destino=b)
        prep.commit()
    try:
        with pytest.raises(Exception, match="apagaria dados"):
            command.downgrade(Config(str(RAIZ / "alembic.ini")), "0004")
        # o downgrade roda numa transação só: a falha na 0005 desfaz também 0010 a 0006
        assert _revisao(esquema) == "0010"
        with psycopg.connect(esquema) as ver:
            linha = ver.execute(
                "SELECT count(*) FROM transacao_versao WHERE user_id = %s", (uid,)
            ).fetchone()
        assert linha == (2,)  # as duas pernas continuam lá
    finally:
        apagar_usuario(esquema, uid)
