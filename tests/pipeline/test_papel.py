"""SPEC-014-AC-8: o papel do pipeline não escreve em nada e executa só as leituras da 0014."""

from __future__ import annotations

import psycopg
import pytest

pytestmark = pytest.mark.banco

LEITURAS_0014 = {
    "saldo_derivado",
    "r4_divergencias",
    "fatura_resumo",
    "fatura_itens",
    "limite_linha",
    "a_receber_pessoas",
    "mes_inicio",
    "gasto_real_itens",
    "gasto_real",
    "gasto_real_por_conta",
    "reserva_nivel",
    "reserva_cobertura",
    "reserva_aporte",
    "reserva_meses_ate",
    "reserva_situacao",
}


def test_papel_sem_escrita_e_execute_minimo(esquema: str, url_pipeline: str) -> None:
    with psycopg.connect(url_pipeline) as pipe:
        tabelas = [
            r[0]
            for r in pipe.execute(
                "SELECT c.relname FROM pg_class c WHERE c.relnamespace = 'public'::regnamespace "
                "AND c.relkind IN ('r', 'v', 'p') ORDER BY 1"
            ).fetchall()
        ]
        assert "transacao_versao" in tabelas and "alembic_version" in tabelas
        for t in tabelas:
            for priv in ("INSERT", "UPDATE", "DELETE", "TRUNCATE"):
                ok = pipe.execute("SELECT has_table_privilege(current_user, %s, %s)", (t, priv))
                assert ok.fetchone() == (False,), f"pipeline tem {priv} em {t}"
        # o nome da pessoa e o da conta jamais são lidos: pessoa.nome segue negado (ADR 045)
        nome = pipe.execute(
            "SELECT has_column_privilege(current_user, 'pessoa', 'nome', 'SELECT')"
        ).fetchone()
        assert nome == (False,)
    with psycopg.connect(esquema) as dono:
        concedidas = {
            r[0]
            for r in dono.execute(
                "SELECT p.proname FROM pg_proc p, aclexplode(p.proacl) a "
                "WHERE p.pronamespace = 'public'::regnamespace "
                "AND a.grantee = 'abako_pipeline'::regrole AND a.privilege_type = 'EXECUTE'"
            ).fetchall()
        }
        dono.rollback()
    assert concedidas == LEITURAS_0014
    with psycopg.connect(url_pipeline) as pipe:
        for escrita in (
            "lancamento_gravar", "lancamento_excluir", "conta_gravar", "pessoa_gravar",
            "estorno_gravar", "alertas", "r2_situacao", "vale_situacao", "receita_total",
        ):  # fmt: skip
            existe = pipe.execute(
                "SELECT bool_or(has_function_privilege(p.oid, 'EXECUTE')) FROM pg_proc p "
                "WHERE p.proname = %s AND p.pronamespace = 'public'::regnamespace",
                (escrita,),
            ).fetchone()
            assert existe == (False,), escrita
        # as funções concedidas rodam INVOKER (com os privilégios do pipeline, não do dono)
        definers = pipe.execute(
            "SELECT p.proname FROM pg_proc p WHERE p.proname = ANY(%s) AND p.prosecdef",
            (sorted(LEITURAS_0014),),
        ).fetchall()
        assert definers == []
