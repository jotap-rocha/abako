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
        # ADR 042: nas tabelas de versão a aplicação só lê; a escrita passa pelas funções.
        for t in tabelas:
            assert _tem_privilegio(app, t, "SELECT")
            for priv in ("INSERT", "UPDATE", "DELETE", "TRUNCATE"):
                assert not _tem_privilegio(app, t, priv), f"app tem {priv} em {t}"

        # Comportamento real: INSERT/UPDATE/DELETE diretos são negados; a função grava.
        linha = app.execute(
            "INSERT INTO usuario (login) VALUES ('u_papel_app') RETURNING user_id"
        ).fetchone()
        assert linha is not None
        uid = linha[0]
        diretos = (
            "INSERT INTO conta_versao (user_id, conta_id, nome) VALUES (%s, 910, 'c')",
            "INSERT INTO transacao_versao (user_id, conta_id, data_transacao, valor, tipo) "
            "VALUES (%s, 910, DATE '2026-01-05', 5.00, 'receita')",
        )
        for comando in diretos:
            with pytest.raises(psycopg.errors.InsufficientPrivilege):
                app.execute(comando, (uid,))
            app.rollback()
            linha = app.execute(
                "INSERT INTO usuario (login) VALUES ('u_papel_app') RETURNING user_id"
            ).fetchone()
            assert linha is not None
            uid = linha[0]
        conta = app.execute(
            "SELECT conta_id FROM conta_gravar(%s, NULL, NULL, 'c', 'corrente', NULL)", (uid,)
        ).fetchone()
        assert conta is not None
        app.rollback()
        for t in tabelas:
            for comando in (f"UPDATE {t} SET vigente = false", f"DELETE FROM {t}"):
                with pytest.raises(psycopg.errors.InsufficientPrivilege):
                    app.execute(comando)
                app.rollback()


FUNCOES_DE_ESCRITA = (
    "conta_gravar(bigint, bigint, integer, text, text, bigint)",
    "lancamento_gravar(bigint, bigint, integer, text, date, numeric, bigint, bigint, numeric, "
    "numeric, text, text, text)",
    "lancamento_excluir(bigint, bigint, integer)",
)


def test_escrita_so_pelas_funcoes(esquema: str, url_app: str, url_pipeline: str) -> None:
    """ADR 042: o app executa as funções de escrita; o pipeline não executa nenhuma."""
    with psycopg.connect(url_app) as app, psycopg.connect(url_pipeline) as pipe:
        for funcao in FUNCOES_DE_ESCRITA:
            linha = app.execute("SELECT has_function_privilege(%s, 'EXECUTE')", (funcao,))
            assert linha.fetchone() == (True,), funcao
            linha = pipe.execute("SELECT has_function_privilege(%s, 'EXECUTE')", (funcao,))
            assert linha.fetchone() == (False,), funcao
        for auxiliar in ("abako_erro(text, text)",):
            linha = app.execute("SELECT has_function_privilege(%s, 'EXECUTE')", (auxiliar,))
            assert linha.fetchone() == (False,), auxiliar
        for sequencia in ("conta_id_seq", "transacao_id_seq"):
            linha = app.execute("SELECT has_sequence_privilege(%s, 'USAGE')", (sequencia,))
            assert linha.fetchone() == (False,), sequencia


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
