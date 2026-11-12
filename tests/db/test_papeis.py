"""SPEC-001-AC-9: `app` sem UPDATE/DELETE nas tabelas de versão; `pipeline` só leitura.

Conecta como os papéis reais (URLs validadas pelo mesmo guarda do tst, ver conftest).
"""

from __future__ import annotations

from decimal import Decimal

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
        assert tabelas == ["conta_versao", "linha_credito", "pessoa", "transacao_versao"]
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
    "conta_gravar(bigint, bigint, integer, text, text, bigint, bigint)",
    "lancamento_gravar(bigint, bigint, integer, text, date, numeric, bigint, bigint, numeric, "
    "numeric, text, text, text, integer, bigint)",
    "lancamento_excluir(bigint, bigint, integer)",
    "pessoa_gravar(bigint, bigint, integer, text)",
    "pessoa_excluir(bigint, bigint, integer)",
    "linha_credito_gravar(bigint, bigint, integer, text, numeric)",
    "fechamento_gravar(bigint, bigint, integer, date)",
)

TABELAS_DO_CARTAO = ("linha_credito", "cartao_fechamento")


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
        sequencias = ("conta_id_seq", "transacao_id_seq", "linha_credito_id_seq", "pessoa_id_seq")
        for sequencia in sequencias:
            linha = app.execute("SELECT has_sequence_privilege(%s, 'USAGE')", (sequencia,))
            assert linha.fetchone() == (False,), sequencia


def test_tabelas_do_cartao_so_leitura(esquema: str, url_app: str, url_pipeline: str) -> None:
    """SPEC-005: app e pipeline só leem as tabelas novas; a escrita é pelas funções."""
    with psycopg.connect(url_app) as app, psycopg.connect(url_pipeline) as pipe:
        for papel in (app, pipe):
            for t in TABELAS_DO_CARTAO:
                assert _tem_privilegio(papel, t, "SELECT"), t
                for priv in ("INSERT", "UPDATE", "DELETE", "TRUNCATE"):
                    assert not _tem_privilegio(papel, t, priv), f"{priv} em {t}"
        # o app grava pelas funções (a SECURITY DEFINER escreve como dono)
        linha = app.execute(
            "INSERT INTO usuario (login) VALUES ('u_papel_cartao') RETURNING user_id"
        ).fetchone()
        assert linha is not None
        uid = linha[0]
        lin = app.execute(
            "SELECT linha_id FROM linha_credito_gravar(%s, NULL, NULL, 'l', 100.00)", (uid,)
        ).fetchone()
        assert lin is not None
        card = app.execute(
            "SELECT conta_id FROM conta_gravar(%s, NULL, NULL, 'c', 'divida', NULL, %s)",
            (uid, lin[0]),
        ).fetchone()
        assert card is not None
        app.execute("SELECT fechamento_gravar(%s, %s, 10, DATE '2025-01-01')", (uid, card[0]))
        app.rollback()  # nada fica no banco
        with pytest.raises(psycopg.errors.InsufficientPrivilege):
            app.execute("INSERT INTO linha_credito (user_id, nome, limite) VALUES (1, 'x', 1.00)")
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


FUNCOES_DE_LEITURA_DO_GASTO_REAL = (
    "mes_inicio(text)",
    "gasto_real_itens(bigint, text)",
    "gasto_real(bigint, text)",
    "gasto_real_por_conta(bigint, text)",
    "receita_caixa(bigint, text)",
    "receita_beneficio(bigint, text)",
    "receita_total(bigint, text)",
)


def test_leituras_do_gasto_real_so_o_app(esquema: str, url_app: str, url_pipeline: str) -> None:
    """SPEC-008 / ADR 046: o app executa as leituras (INVOKER, sem escrita); o pipeline não."""
    with psycopg.connect(url_app) as app, psycopg.connect(url_pipeline) as pipe:
        for funcao in FUNCOES_DE_LEITURA_DO_GASTO_REAL:
            linha = app.execute("SELECT has_function_privilege(%s, 'EXECUTE')", (funcao,))
            assert linha.fetchone() == (True,), funcao
            linha = pipe.execute("SELECT has_function_privilege(%s, 'EXECUTE')", (funcao,))
            assert linha.fetchone() == (False,), funcao
            invoker = app.execute(
                "SELECT NOT prosecdef FROM pg_proc WHERE oid = %s::regprocedure", (funcao,)
            ).fetchone()
            assert invoker == (True,), funcao  # roda com os privilégios de quem chama
        # o app lê o que escreveu pelas funções e o gasto real sai pelo papel dele
        novo = app.execute(
            "INSERT INTO usuario (login) VALUES ('u_papel_gasto') RETURNING user_id"
        ).fetchone()
        assert novo is not None
        uid = novo[0]
        corrente = app.execute(
            "SELECT conta_id FROM conta_gravar(%s, NULL, NULL, 'c', 'corrente', NULL)", (uid,)
        ).fetchone()
        assert corrente is not None
        app.execute(
            "SELECT * FROM lancamento_gravar(%s, NULL, NULL, 'debito', DATE '2025-04-08', 12.34, "
            "%s, NULL, NULL, NULL, NULL, NULL, NULL, NULL)",
            (uid, corrente[0]),
        )
        assert app.execute("SELECT gasto_real(%s, '2025-04')", (uid,)).fetchone() == (
            Decimal("12.34"),
        )
        app.rollback()  # nada fica no banco
        for papel in (app, pipe):
            for priv in ("UPDATE", "DELETE"):
                assert not _tem_privilegio(papel, "transacao_versao", priv), priv
        with pytest.raises(psycopg.errors.InsufficientPrivilege):
            pipe.execute("SELECT gasto_real(1, '2025-04')")
        pipe.rollback()
