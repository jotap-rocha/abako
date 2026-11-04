"""Snapshot é âncora imutável: `app` só lê e insere; `pipeline` só lê (ADR 026/036/041)."""

from __future__ import annotations

import psycopg
import pytest

pytestmark = pytest.mark.banco


def _tem(conn: psycopg.Connection, objeto: str, priv: str) -> bool:
    linha = conn.execute(
        "SELECT has_table_privilege(current_user, %s, %s)", (objeto, priv)
    ).fetchone()
    assert linha is not None
    return bool(linha[0])


def test_app_nao_altera_nem_apaga_snapshot(esquema: str, url_app: str) -> None:
    with psycopg.connect(url_app) as app:
        assert _tem(app, "snapshot_saldo", "SELECT") and _tem(app, "snapshot_saldo", "INSERT")
        for priv in ("UPDATE", "DELETE", "TRUNCATE"):
            assert not _tem(app, "snapshot_saldo", priv), priv
        for comando in ("UPDATE snapshot_saldo SET valor = 0", "DELETE FROM snapshot_saldo"):
            with pytest.raises(psycopg.errors.InsufficientPrivilege):
                app.execute(comando)
            app.rollback()


def test_pipeline_so_le_snapshot_e_views(esquema: str, url_pipeline: str) -> None:
    with psycopg.connect(url_pipeline) as pipe:
        for objeto in ("snapshot_saldo", "snapshot_vigente", "transacao_vigente"):
            assert _tem(pipe, objeto, "SELECT"), objeto
        for priv in ("INSERT", "UPDATE", "DELETE", "TRUNCATE"):
            assert not _tem(pipe, "snapshot_saldo", priv), priv
