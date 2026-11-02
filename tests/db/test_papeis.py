"""SPEC-001-AC-9: `app` sem UPDATE/DELETE nas tabelas de versão; `pipeline` só leitura.

Conecta como os papéis reais (URLs validadas pelo mesmo guarda do tst, ver conftest).
"""

from __future__ import annotations

import psycopg
import pytest

pytestmark = pytest.mark.banco


def _tem_privilegio(conn: psycopg.Connection, tabela: str, priv: str) -> bool:
    linha = conn.execute(
        "SELECT has_table_privilege(current_user, %s, %s)", (tabela, priv)
    ).fetchone()
    assert linha is not None
    return bool(linha[0])


def test_app_sem_update_delete(esquema: str, url_app: str) -> None:
    with psycopg.connect(url_app) as app:
        # Tabelas de versão = as que têm a coluna `vigente`.
        tabelas = [
            r[0]
            for r in app.execute(
                "SELECT table_name FROM information_schema.columns "
                "WHERE table_schema = 'public' AND column_name = 'vigente' ORDER BY 1"
            ).fetchall()
        ]
        assert tabelas == ["conta_versao", "transacao_versao"]
        for t in tabelas:
            for priv in ("UPDATE", "DELETE", "TRUNCATE"):
                assert not _tem_privilegio(app, t, priv), f"app tem {priv} em {t}"
            assert _tem_privilegio(app, t, "INSERT")

        # Comportamento real: INSERT funciona; UPDATE/DELETE são negados.
        linha = app.execute(
            "INSERT INTO usuario (login) VALUES ('u_papel_app') RETURNING user_id"
        ).fetchone()
        assert linha is not None
        uid = linha[0]
        app.execute(
            "INSERT INTO conta_versao (user_id, conta_id, nome) VALUES (%s, 910, 'c')", (uid,)
        )
        app.execute(
            "INSERT INTO transacao_versao (user_id, conta_id, data_transacao, valor) "
            "VALUES (%s, 910, DATE '2026-01-05', 5.00)",
            (uid,),
        )
        app.rollback()
        for t in tabelas:
            for comando in (f"UPDATE {t} SET vigente = false", f"DELETE FROM {t}"):
                with pytest.raises(psycopg.errors.InsufficientPrivilege):
                    app.execute(comando)
                app.rollback()


def test_pipeline_somente_leitura(esquema: str, url_pipeline: str) -> None:
    with psycopg.connect(url_pipeline) as pipe:
        for t in ("usuario", "conta_versao", "transacao_versao"):
            assert _tem_privilegio(pipe, t, "SELECT")
            for priv in ("INSERT", "UPDATE", "DELETE", "TRUNCATE"):
                assert not _tem_privilegio(pipe, t, priv), f"pipeline tem {priv} em {t}"
        # O papel é read-only por padrão (transação) além de sem privilégio de escrita.
        with pytest.raises(
            (psycopg.errors.ReadOnlySqlTransaction, psycopg.errors.InsufficientPrivilege)
        ):
            pipe.execute("INSERT INTO usuario (login) VALUES ('x')")
        pipe.rollback()
