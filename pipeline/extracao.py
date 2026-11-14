"""Leitura do transacional pelo papel somente leitura (INV-15).

A regra financeira fica nas funções SQL (ADR 015): aqui só se enumera o que consultar (usuários,
contas, meses, competências) e se chama a função. Nenhuma consulta seleciona `descricao`, nome de
conta, de pessoa ou de recorrente; só ids, datas e valores. Todas rodam na mesma transação
REPEATABLE READ, então os agregados vêm do mesmo retrato do banco.
"""

from __future__ import annotations

from datetime import date
from typing import Any

import psycopg

Linhas = list[tuple[Any, ...]]


def usuarios(conn: psycopg.Connection, filtro: tuple[int, ...] | None) -> list[int]:
    lista = list(filtro) if filtro is not None else None
    linhas = conn.execute(
        "SELECT user_id FROM usuario WHERE %s::bigint[] IS NULL OR user_id = ANY(%s::bigint[]) "
        "ORDER BY user_id",
        (lista, lista),
    ).fetchall()
    return [int(r[0]) for r in linhas]


def saldo_diario(conn: psycopg.Connection, uids: list[int], hoje: date) -> Linhas:
    """Um saldo por conta e dia, do primeiro snapshot ou lançamento até hoje (saldo_derivado)."""
    return conn.execute(
        """
        WITH ini AS (
            SELECT c.user_id, c.conta_id,
                   least(
                       (SELECT min(s.data_snapshot) FROM snapshot_vigente s
                        WHERE s.user_id = c.user_id AND s.conta_id = c.conta_id),
                       (SELECT min(t.data_transacao) FROM transacao_vigente t
                        WHERE t.user_id = c.user_id AND t.conta_id = c.conta_id)
                   ) AS inicio
            FROM conta_versao c
            WHERE c.user_id = ANY(%s) AND c.vigente AND NOT c.excluida
        )
        SELECT i.user_id, i.conta_id, d::date,
               saldo_derivado(i.user_id, i.conta_id, d::date)
        FROM ini i
        CROSS JOIN LATERAL generate_series(i.inicio::timestamp, %s::timestamp, interval '1 day') d
        WHERE i.inicio IS NOT NULL
        ORDER BY i.user_id, i.conta_id, d
        """,
        (uids, hoje),
    ).fetchall()


def _meses(alias: str = "m") -> str:
    return f"""
        {alias} AS (
            SELECT user_id, to_char(data_transacao, 'YYYY-MM') AS mes
            FROM transacao_vigente WHERE user_id = ANY(%s)
            UNION
            SELECT user_id, competencia
            FROM transacao_vigente WHERE user_id = ANY(%s) AND competencia IS NOT NULL
        )
    """


def gasto_mensal(conn: psycopg.Connection, uids: list[int]) -> Linhas:
    return conn.execute(
        f"""
        WITH {_meses()}
        SELECT m.user_id, m.mes, g.conta_id, g.valor
        FROM m CROSS JOIN LATERAL gasto_real_por_conta(m.user_id, m.mes) g
        ORDER BY m.user_id, m.mes, g.conta_id
        """,  # noqa: S608
        (uids, uids),
    ).fetchall()


def gasto_total_por_mes(conn: psycopg.Connection, uids: list[int]) -> Linhas:
    """Conferência: gasto_real (total do mês) para cada (usuário, mês) com movimento."""
    return conn.execute(
        f"""
        WITH {_meses()}
        SELECT m.user_id, m.mes, gasto_real(m.user_id, m.mes)
        FROM m ORDER BY m.user_id, m.mes
        """,  # noqa: S608
        (uids, uids),
    ).fetchall()


def fatura_resumo(conn: psycopg.Connection, uids: list[int]) -> Linhas:
    return conn.execute(
        """
        WITH pares AS (
            SELECT DISTINCT user_id, conta_id, competencia
            FROM transacao_vigente
            WHERE user_id = ANY(%s) AND competencia IS NOT NULL
              AND tipo IN ('credito', 'estorno')
        )
        SELECT p.user_id, p.conta_id, p.competencia, r.total, r.propria, r.terceiros
        FROM pares p
        CROSS JOIN LATERAL fatura_resumo(p.user_id, p.conta_id, p.competencia) r
        ORDER BY p.user_id, p.conta_id, p.competencia
        """,
        (uids,),
    ).fetchall()


def limite_linha(conn: psycopg.Connection, uids: list[int], hoje: date) -> Linhas:
    return conn.execute(
        """
        WITH l AS (
            SELECT DISTINCT user_id, linha_id FROM linha_credito
            WHERE user_id = ANY(%s) AND vigente AND NOT excluida
        )
        SELECT l.user_id, l.linha_id, r.limite, r.usado, r.disponivel
        FROM l CROSS JOIN LATERAL limite_linha(l.user_id, l.linha_id, %s) r
        ORDER BY l.user_id, l.linha_id
        """,
        (uids, hoje),
    ).fetchall()


def cobertura_reserva(conn: psycopg.Connection, uids: list[int], hoje: date) -> Linhas:
    return conn.execute(
        """
        SELECT u.user_id, r.contas_reserva, r.saldo_liquido, r.imposto_acumulado, r.saldo_bruto,
               r.meses_meta, r.gasto_essencial, r.meta, r.nivel, r.falta, r.cobertura_meses,
               r.data_alvo, r.meses_ate_alvo, r.alvo_vencida, r.aporte_mensal, r.config_pendente
        FROM unnest(%s::bigint[]) AS u(user_id)
        CROSS JOIN LATERAL reserva_situacao(u.user_id, %s) r
        ORDER BY u.user_id
        """,
        (uids, hoje),
    ).fetchall()


def a_receber(conn: psycopg.Connection, uids: list[int]) -> Linhas:
    """Só o total por usuário: nenhuma pessoa, nem por id (ADR 045/054)."""
    return conn.execute(
        """
        SELECT u.user_id,
               COALESCE((SELECT sum(a.a_receber) FROM a_receber_pessoas(u.user_id, NULL) a), 0.00)
        FROM unnest(%s::bigint[]) AS u(user_id)
        ORDER BY u.user_id
        """,
        (uids,),
    ).fetchall()


def divergencias_r4(conn: psycopg.Connection, uids: list[int]) -> int:
    """Quantidade de divergências R4 (só contagem; o log nunca leva valor nem conta)."""
    total = 0
    for uid in uids:
        linha = conn.execute("SELECT count(*) FROM r4_divergencias(%s)", (uid,)).fetchone()
        total += int(linha[0]) if linha else 0
    return total
