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
        assert tabelas == [
            "conta_versao",
            "linha_credito",
            "pessoa",
            "recorrente",
            "transacao_versao",
        ]
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
    "numeric, text, text, text, integer, bigint, text)",
    "lancamento_excluir(bigint, bigint, integer)",
    "pessoa_gravar(bigint, bigint, integer, text)",
    "pessoa_excluir(bigint, bigint, integer)",
    "linha_credito_gravar(bigint, bigint, integer, text, numeric)",
    "fechamento_gravar(bigint, bigint, integer, date)",
    "reserva_parametro_gravar(bigint, integer, numeric, date, date)",
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


FUNCOES_DE_LEITURA_DA_RESERVA = (
    "reserva_nivel(numeric, numeric)",
    "reserva_cobertura(numeric, numeric)",
    "reserva_aporte(numeric, integer)",
    "reserva_meses_ate(date, date)",
    "reserva_situacao(bigint, date)",
)
TABELAS_DA_RESERVA = ("reserva_parametro", "reserva_parametro_vigente")


def test_reserva_papeis(esquema: str, url_app: str, url_pipeline: str) -> None:
    """SPEC-009 / ADR 047: app executa e grava só pela função; pipeline só lê a tabela."""
    with psycopg.connect(url_app) as app, psycopg.connect(url_pipeline) as pipe:
        for papel in (app, pipe):
            for t in TABELAS_DA_RESERVA:
                assert _tem_privilegio(papel, t, "SELECT"), t
                for priv in ("INSERT", "UPDATE", "DELETE", "TRUNCATE"):
                    assert not _tem_privilegio(papel, t, priv), f"{priv} em {t}"
        for funcao in FUNCOES_DE_LEITURA_DA_RESERVA:
            assert app.execute(
                "SELECT has_function_privilege(%s, 'EXECUTE')", (funcao,)
            ).fetchone() == (True,)
            assert pipe.execute(
                "SELECT has_function_privilege(%s, 'EXECUTE')", (funcao,)
            ).fetchone() == (False,)
            invoker = app.execute(
                "SELECT NOT prosecdef FROM pg_proc WHERE oid = %s::regprocedure", (funcao,)
            ).fetchone()
            assert invoker == (True,), funcao
        definer = app.execute(
            "SELECT prosecdef, proconfig FROM pg_proc WHERE oid = %s::regprocedure",
            ("reserva_parametro_gravar(bigint, integer, numeric, date, date)",),
        ).fetchone()
        assert definer is not None and definer[0] is True
        assert definer[1] == ["search_path=public, pg_temp"]
        # o app grava pelo papel dele, pela função, e lê a situação
        novo = app.execute(
            "INSERT INTO usuario (login) VALUES ('u_papel_reserva') RETURNING user_id"
        ).fetchone()
        assert novo is not None
        uid = novo[0]
        app.execute(
            "SELECT reserva_parametro_gravar(%s, 3, 1000.00, NULL, DATE '2026-01-01')", (uid,)
        )
        linha = app.execute(
            "SELECT meta, config_pendente FROM reserva_situacao(%s, DATE '2026-04-01')", (uid,)
        ).fetchone()
        assert linha == (Decimal("3000.00"), False)
        with pytest.raises(psycopg.errors.InsufficientPrivilege):
            app.execute(
                "INSERT INTO reserva_parametro (user_id, meses, gasto_essencial, "
                "vigente_desde) VALUES (%s, 3, 1.00, DATE '2026-01-01')",
                (uid,),
            )
        app.rollback()  # nada fica no banco
        with pytest.raises(psycopg.errors.InsufficientPrivilege):
            pipe.execute("SELECT * FROM reserva_situacao(1, DATE '2026-04-01')")
        pipe.rollback()
        with pytest.raises(psycopg.errors.InsufficientPrivilege):
            pipe.execute("SELECT reserva_parametro_gravar(1, 3, 1.00, NULL, DATE '2026-01-01')")
        pipe.rollback()


FUNCOES_DE_LEITURA_DO_R2 = (
    "data_no_mes(integer, date)",
    "meses_entre(date, date)",
    "ocorrencias_do_mes(bigint, text)",
    "fatura_fechamento(bigint, bigint, text)",
    "vencimento_fatura(bigint, bigint, text)",
    "r2_horizonte(bigint, date)",
    "pool_pago_ate(bigint, bigint, date)",
    "alocacao_pago_ate(bigint, bigint, date)",
    "r2_itens(bigint, date)",
    "r2_situacao(bigint, date)",
)
FUNCOES_DE_ESCRITA_DO_R2 = (
    "recorrente_gravar(bigint, bigint, integer, text, text, numeric, integer, bigint, text, text)",
    "recorrente_excluir(bigint, bigint, integer)",
    "recorrente_vincular(bigint, bigint, text, bigint)",
    "recorrente_desvincular(bigint, bigint, text)",
    "r2_parametro_gravar(bigint, integer, date)",
    "vencimento_gravar(bigint, bigint, integer, date)",
)
TABELAS_DO_R2 = (
    "recorrente",
    "recorrente_vigente",
    "recorrente_vinculo",
    "recorrente_vinculo_vigente",
    "recorrente_vinculo_efetivo",
    "r2_parametro",
    "r2_parametro_vigente",
    "cartao_vencimento",
    "vencimento_vigente",
)
TABELAS_DO_R2_PARA_O_PIPELINE = (
    "r2_parametro",
    "r2_parametro_vigente",
    "cartao_vencimento",
    "vencimento_vigente",
)


def test_r2_papeis(esquema: str, url_app: str, url_pipeline: str) -> None:
    """SPEC-010 / ADR 048: app executa e grava só pelas funções; pipeline só lê (sem o nome)."""
    with psycopg.connect(url_app) as app, psycopg.connect(url_pipeline) as pipe:
        for t in TABELAS_DO_R2:
            assert _tem_privilegio(app, t, "SELECT"), t
            for priv in ("INSERT", "UPDATE", "DELETE", "TRUNCATE"):
                assert not _tem_privilegio(app, t, priv), f"app tem {priv} em {t}"
        for t in TABELAS_DO_R2_PARA_O_PIPELINE:
            assert _tem_privilegio(pipe, t, "SELECT"), t
        for t in TABELAS_DO_R2:
            for priv in ("INSERT", "UPDATE", "DELETE", "TRUNCATE"):
                assert not _tem_privilegio(pipe, t, priv), f"pipeline tem {priv} em {t}"
        # recorrente e vínculo (nome, valor, dia, conta) não chegam ao pipeline (ADR 048 item 12)
        for t in ("recorrente", "recorrente_vigente", "recorrente_vinculo"):
            assert not _tem_privilegio(pipe, t, "SELECT"), t
        assert pipe.execute(
            "SELECT has_column_privilege(current_user, 'recorrente', 'nome', 'SELECT')"
        ).fetchone() == (False,)
        for funcao in (*FUNCOES_DE_LEITURA_DO_R2, *FUNCOES_DE_ESCRITA_DO_R2):
            assert app.execute(
                "SELECT has_function_privilege(%s, 'EXECUTE')", (funcao,)
            ).fetchone() == (True,), funcao
            assert pipe.execute(
                "SELECT has_function_privilege(%s, 'EXECUTE')", (funcao,)
            ).fetchone() == (False,), funcao
        for funcao in FUNCOES_DE_LEITURA_DO_R2:
            invoker = app.execute(
                "SELECT NOT prosecdef FROM pg_proc WHERE oid = %s::regprocedure", (funcao,)
            ).fetchone()
            assert invoker == (True,), funcao
        for funcao in FUNCOES_DE_ESCRITA_DO_R2:
            definer = app.execute(
                "SELECT prosecdef, proconfig FROM pg_proc WHERE oid = %s::regprocedure", (funcao,)
            ).fetchone()
            assert definer == (True, ["search_path=public, pg_temp"]), funcao
        assert app.execute(
            "SELECT has_sequence_privilege('recorrente_id_seq', 'USAGE')"
        ).fetchone() == (False,)

        # o app grava pelo papel dele, só pelas funções, e lê a situação
        novo = app.execute(
            "INSERT INTO usuario (login) VALUES ('u_papel_r2') RETURNING user_id"
        ).fetchone()
        assert novo is not None
        uid = novo[0]
        corrente = app.execute(
            "SELECT conta_id FROM conta_gravar(%s, NULL, NULL, 'c', 'corrente', NULL)", (uid,)
        ).fetchone()
        assert corrente is not None
        app.execute("SELECT r2_parametro_gravar(%s, 15, DATE '2026-01-01')", (uid,))
        rec = app.execute(
            "SELECT recorrente_id FROM recorrente_gravar("
            "%s, NULL, NULL, 'aluguel', 'fixo', 300.00, 12, %s, '2026-05', NULL)",
            (uid, corrente[0]),
        ).fetchone()
        assert rec is not None
        pago = app.execute(
            "SELECT transacao_id FROM lancamento_gravar("
            "%s, NULL, NULL, 'debito', DATE '2026-05-08', 300.00, %s, "
            "NULL, NULL, NULL, NULL, NULL, NULL, NULL, NULL)",
            (uid, corrente[0]),
        ).fetchone()
        assert pago is not None
        antes = app.execute(
            "SELECT horizonte_dias, fixos_pendentes FROM r2_situacao(%s, DATE '2026-05-10')",
            (uid,),
        ).fetchone()
        assert antes == (15, Decimal("300.00"))
        app.execute("SELECT recorrente_vincular(%s, %s, '2026-05', %s)", (uid, rec[0], pago[0]))
        depois = app.execute(
            "SELECT fixos_pendentes FROM r2_situacao(%s, DATE '2026-05-10')", (uid,)
        ).fetchone()
        assert depois == (Decimal("0.00"),)
        for comando in (
            "INSERT INTO recorrente (user_id, nome, tipo, valor, dia, conta_id, mes_inicio) "
            "VALUES (%s, 'x', 'fixo', 1.00, 5, 1, DATE '2026-05-01')",
            "INSERT INTO recorrente_vinculo (user_id, recorrente_id, mes) "
            "VALUES (%s, 1, DATE '2026-05-01')",
            "INSERT INTO r2_parametro (user_id, dias, vigente_desde) "
            "VALUES (%s, 5, DATE '2026-01-01')",
            "INSERT INTO cartao_vencimento (user_id, conta_id, dia, vigente_desde) "
            "VALUES (%s, 1, 5, DATE '2026-01-01')",
            "UPDATE recorrente SET vigente = false WHERE user_id = %s",
            "DELETE FROM recorrente_vinculo WHERE user_id = %s",
        ):
            with pytest.raises(psycopg.errors.InsufficientPrivilege):
                app.execute(comando, (uid,))
            app.rollback()  # nada fica no banco (a transação inteira é desfeita)
            novo = app.execute("SELECT 1").fetchone()
            assert novo == (1,)
        app.rollback()
        with pytest.raises(psycopg.errors.InsufficientPrivilege):
            pipe.execute("SELECT * FROM r2_situacao(1, DATE '2026-05-10')")
        pipe.rollback()
        with pytest.raises(psycopg.errors.InsufficientPrivilege):
            pipe.execute("SELECT * FROM recorrente_vinculo")
        pipe.rollback()
        with pytest.raises(psycopg.errors.InsufficientPrivilege):
            pipe.execute("SELECT r2_parametro_gravar(1, 5, DATE '2026-01-01')")
        pipe.rollback()


def test_alertas_papeis(esquema: str, url_app: str, url_pipeline: str) -> None:
    """SPEC-011 / ADR 049: só o app executa `alertas`; é INVOKER e não cria tabela nem escrita."""
    funcao = "alertas(bigint, date)"
    with psycopg.connect(url_app) as app, psycopg.connect(url_pipeline) as pipe:
        assert app.execute(
            "SELECT has_function_privilege(%s, 'EXECUTE')", (funcao,)
        ).fetchone() == (True,)
        assert pipe.execute(
            "SELECT has_function_privilege(%s, 'EXECUTE')", (funcao,)
        ).fetchone() == (False,)
        assert app.execute(
            "SELECT NOT prosecdef, provolatile = 's' FROM pg_proc WHERE oid = %s::regprocedure",
            (funcao,),
        ).fetchone() == (True, True)
        novo = app.execute(
            "INSERT INTO usuario (login) VALUES ('u_papel_alertas') RETURNING user_id"
        ).fetchone()
        assert novo is not None
        itens = app.execute(
            "SELECT codigo, severidade FROM alertas(%s, DATE '2026-05-10')", (novo[0],)
        ).fetchall()
        assert itens == [("CONFIG", "baixa")]
        app.rollback()
        with pytest.raises(psycopg.errors.InsufficientPrivilege):
            pipe.execute("SELECT * FROM alertas(1, DATE '2026-05-10')")
        pipe.rollback()


FUNCOES_DE_LEITURA_DO_VALE = (
    "vale_conta_em(bigint, date)",
    "vale_mes(bigint, date, numeric, numeric)",
    "vale_calculo(bigint, date)",
    "vale_situacao(bigint, text, date)",
    "beneficios_contas(bigint, text, date)",
)
FUNCOES_DE_ESCRITA_DO_VALE = (
    "vale_parametro_gravar(bigint, bigint, numeric, text, date)",
    "vale_decisao_gravar(bigint, text, text)",
)
TABELAS_DO_VALE = (
    "vale_parametro",
    "vale_parametro_vigente",
    "vale_bolso",
    "vale_decisao",
    "vale_decisao_vigente",
)


def test_vale_papeis(esquema: str, url_app: str, url_pipeline: str) -> None:
    """SPEC-013 / ADR 052: app lê e escreve só pelas funções; pipeline não recebe nada novo."""
    with psycopg.connect(url_app) as app, psycopg.connect(url_pipeline) as pipe:
        for t in TABELAS_DO_VALE:
            assert _tem_privilegio(app, t, "SELECT"), t
            for priv in ("INSERT", "UPDATE", "DELETE", "TRUNCATE"):
                assert not _tem_privilegio(app, t, priv), f"app tem {priv} em {t}"
            for priv in ("SELECT", "INSERT", "UPDATE", "DELETE", "TRUNCATE"):
                assert not _tem_privilegio(pipe, t, priv), f"pipeline tem {priv} em {t}"
        for funcao in (*FUNCOES_DE_LEITURA_DO_VALE, *FUNCOES_DE_ESCRITA_DO_VALE):
            assert app.execute(
                "SELECT has_function_privilege(%s, 'EXECUTE')", (funcao,)
            ).fetchone() == (True,), funcao
            assert pipe.execute(
                "SELECT has_function_privilege(%s, 'EXECUTE')", (funcao,)
            ).fetchone() == (False,), funcao
        for funcao in FUNCOES_DE_LEITURA_DO_VALE:
            invoker = app.execute(
                "SELECT NOT prosecdef FROM pg_proc WHERE oid = %s::regprocedure", (funcao,)
            ).fetchone()
            assert invoker == (True,), funcao
        for funcao in FUNCOES_DE_ESCRITA_DO_VALE:
            definer = app.execute(
                "SELECT prosecdef, proconfig FROM pg_proc WHERE oid = %s::regprocedure", (funcao,)
            ).fetchone()
            assert definer == (True, ["search_path=public, pg_temp"]), funcao

        # o app grava pelo papel dele, só pelas funções, e lê a situação
        novo = app.execute(
            "INSERT INTO usuario (login) VALUES ('u_papel_vale') RETURNING user_id"
        ).fetchone()
        assert novo is not None
        uid = novo[0]
        vr = app.execute(
            "SELECT conta_id FROM conta_gravar(%s, NULL, NULL, 'vr', 'beneficio', NULL)", (uid,)
        ).fetchone()
        assert vr is not None
        app.execute(
            "SELECT vale_parametro_gravar(%s, %s, 200.00, 'nenhum', DATE '2025-01-01')",
            (uid, vr[0]),
        )
        app.execute(
            "SELECT * FROM lancamento_gravar(%s, NULL, NULL, 'receita', DATE '2025-01-05', "
            "1000.00, %s, NULL, NULL, NULL, NULL, NULL, NULL, NULL, NULL, NULL)",
            (uid, vr[0]),
        )
        app.execute(
            "SELECT * FROM lancamento_gravar(%s, NULL, NULL, 'debito', DATE '2025-01-10', "
            "150.00, %s, NULL, NULL, NULL, NULL, NULL, NULL, NULL, NULL, 'trabalho')",
            (uid, vr[0]),
        )
        assert app.execute(
            "SELECT vale_decisao_gravar(%s, '2025-01', 'pessoal')", (uid,)
        ).fetchone() == (1,)
        linha = app.execute(
            "SELECT resta_trabalho, sobra FROM vale_situacao(%s, '2025-01', DATE '2025-03-01')",
            (uid,),
        ).fetchone()
        assert linha == (Decimal("50.00"), Decimal("850.00"))
        for comando in (
            "INSERT INTO vale_parametro (user_id, conta_id, base_trabalho, destino_padrao, "
            "vigente_desde) VALUES (%s, 1, 1.00, 'nenhum', DATE '2025-01-01')",
            "INSERT INTO vale_bolso (user_id, transacao_id, versao, bolso) "
            "VALUES (%s, 1, 1, 'pessoal')",
            "INSERT INTO vale_decisao (user_id, mes, destino, versao) "
            "VALUES (%s, DATE '2025-01-01', 'pessoal', 9)",
            "UPDATE vale_decisao SET destino = 'nenhum' WHERE user_id = %s",
            "DELETE FROM vale_bolso WHERE user_id = %s",
        ):
            with pytest.raises(psycopg.errors.InsufficientPrivilege):
                app.execute(comando, (uid,))
            app.rollback()
            # a transação foi desfeita junto: recria o usuário para a próxima tentativa
            novo = app.execute(
                "INSERT INTO usuario (login) VALUES ('u_papel_vale') RETURNING user_id"
            ).fetchone()
            assert novo is not None
            uid = novo[0]
        app.rollback()  # nada fica no banco
        for chamada in (
            "SELECT * FROM vale_situacao(1, '2025-01', DATE '2025-03-01')",
            "SELECT * FROM beneficios_contas(1, '2025-01', DATE '2025-03-01')",
            "SELECT vale_parametro_gravar(1, 1, 1.00, 'nenhum', DATE '2025-01-01')",
            "SELECT vale_decisao_gravar(1, '2025-01', 'pessoal')",
        ):
            with pytest.raises(psycopg.errors.InsufficientPrivilege):
                pipe.execute(chamada)
            pipe.rollback()
