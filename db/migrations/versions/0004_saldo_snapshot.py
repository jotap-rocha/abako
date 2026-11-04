"""saldo derivado, snapshot e R4 (SPEC-003, ADR 041)

Revision ID: 0004
Revises: 0003

SQL puro (ADR 025). A regra de saldo vive aqui, no banco (ADR 015):

- `snapshot_saldo`: âncora observada (o que o app do banco mostra), append-only. O snapshot de
  data D vale para o FIM do dia D. Dois snapshots no mesmo dia: vale o último registrado.
- `snapshot_vigente` e `transacao_vigente`: o que conta (último snapshot do dia; versão vigente
  não excluída). Sem as colunas `vigente`/`excluida`, para não parecerem tabelas de versão.
- `saldo_derivado(user, conta, em)`: último snapshot com data <= em + transações vigentes com
  data > snapshot e <= em. Sem snapshot, parte de zero.
- `r4_divergencias(user)`: para cada snapshot que NÃO é o primeiro da conta, compara o valor com
  o derivado a partir do snapshot anterior. O primeiro snapshot é o saldo inicial (âncora, sem
  comparação). Divergência = derivado - snapshot; tolerância zero. Nunca corrige nada.

As funções recebem o `user_id` explícito (INV-13): quem chama passa o da sessão. Views com
`security_invoker` usam os privilégios de quem consulta.
"""

from alembic import op

revision = "0004"
down_revision = "0003"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        """
        CREATE TABLE snapshot_saldo (
            id            bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
            user_id       bigint  NOT NULL REFERENCES usuario (user_id),
            conta_id      bigint  NOT NULL,
            data_snapshot date    NOT NULL,
            valor         numeric(14, 2) NOT NULL,
            registrado_em timestamptz NOT NULL DEFAULT now()
        )
        """
    )
    op.execute(
        "CREATE INDEX snapshot_saldo_conta_idx ON snapshot_saldo "
        "(user_id, conta_id, data_snapshot, registrado_em)"
    )
    op.execute(
        "CREATE INDEX transacao_versao_conta_data_idx ON transacao_versao "
        "(user_id, conta_id, data_transacao) WHERE vigente AND NOT excluida"
    )

    # Nome de conta único por usuário entre as vigentes (também sob requisições simultâneas).
    op.execute(
        "CREATE UNIQUE INDEX conta_versao_nome_uq ON conta_versao (user_id, lower(nome)) "
        "WHERE vigente AND NOT excluida"
    )
    op.execute(
        """
        CREATE VIEW snapshot_vigente WITH (security_invoker = true) AS
        SELECT DISTINCT ON (user_id, conta_id, data_snapshot)
               id, user_id, conta_id, data_snapshot, valor, registrado_em
        FROM snapshot_saldo
        ORDER BY user_id, conta_id, data_snapshot, registrado_em DESC, id DESC
        """
    )
    op.execute(
        """
        CREATE VIEW transacao_vigente WITH (security_invoker = true) AS
        SELECT id, user_id, transacao_id, versao, conta_id, data_transacao, valor, descricao
        FROM transacao_versao
        WHERE vigente AND NOT excluida
        """
    )

    op.execute(
        """
        CREATE FUNCTION saldo_derivado(p_user bigint, p_conta bigint, p_em date)
        RETURNS numeric
        LANGUAGE sql STABLE AS $$
            WITH base AS (
                SELECT s.data_snapshot, s.valor
                FROM snapshot_vigente s
                WHERE s.user_id = p_user AND s.conta_id = p_conta AND s.data_snapshot <= p_em
                ORDER BY s.data_snapshot DESC
                LIMIT 1
            )
            SELECT COALESCE((SELECT b.valor FROM base b), 0)
                 + COALESCE((
                     SELECT sum(t.valor)
                     FROM transacao_vigente t
                     WHERE t.user_id = p_user AND t.conta_id = p_conta
                       AND t.data_transacao <= p_em
                       AND t.data_transacao >
                           COALESCE((SELECT b.data_snapshot FROM base b), '-infinity'::date)
                 ), 0)
        $$
        """
    )
    op.execute(
        """
        CREATE FUNCTION r4_divergencias(p_user bigint)
        RETURNS TABLE (
            conta_id bigint,
            data_snapshot date,
            valor_snapshot numeric,
            saldo_derivado numeric,
            divergencia numeric
        )
        LANGUAGE sql STABLE AS $$
            WITH s AS (
                SELECT v.conta_id, v.data_snapshot, v.valor,
                       lag(v.data_snapshot) OVER w AS data_anterior,
                       lag(v.valor) OVER w AS valor_anterior
                FROM snapshot_vigente v
                WHERE v.user_id = p_user
                WINDOW w AS (PARTITION BY v.conta_id ORDER BY v.data_snapshot)
            ),
            d AS (
                SELECT s.conta_id, s.data_snapshot, s.valor,
                       s.valor_anterior + COALESCE((
                           SELECT sum(t.valor)
                           FROM transacao_vigente t
                           WHERE t.user_id = p_user AND t.conta_id = s.conta_id
                             AND t.data_transacao > s.data_anterior
                             AND t.data_transacao <= s.data_snapshot
                       ), 0) AS derivado
                FROM s
                WHERE s.data_anterior IS NOT NULL
            )
            SELECT d.conta_id, d.data_snapshot, d.valor, d.derivado, d.derivado - d.valor
            FROM d
            WHERE d.derivado <> d.valor
            ORDER BY d.conta_id, d.data_snapshot
        $$
        """
    )

    op.execute("GRANT SELECT, INSERT ON snapshot_saldo TO abako_app")
    op.execute("GRANT SELECT ON snapshot_saldo TO abako_pipeline")
    op.execute("GRANT SELECT ON snapshot_vigente, transacao_vigente TO abako_app, abako_pipeline")
    # O padrão do Postgres dá EXECUTE a todos; aqui só a aplicação executa.
    op.execute("REVOKE ALL ON FUNCTION saldo_derivado(bigint, bigint, date) FROM PUBLIC")
    op.execute("REVOKE ALL ON FUNCTION r4_divergencias(bigint) FROM PUBLIC")
    op.execute("GRANT EXECUTE ON FUNCTION saldo_derivado(bigint, bigint, date) TO abako_app")
    op.execute("GRANT EXECUTE ON FUNCTION r4_divergencias(bigint) TO abako_app")


def downgrade() -> None:
    op.execute("DROP FUNCTION r4_divergencias(bigint)")
    op.execute("DROP FUNCTION saldo_derivado(bigint, bigint, date)")
    op.execute("DROP VIEW transacao_vigente")
    op.execute("DROP VIEW snapshot_vigente")
    op.execute("DROP INDEX transacao_versao_conta_data_idx")
    op.execute("DROP INDEX IF EXISTS conta_versao_nome_uq")
    op.execute("DROP TABLE snapshot_saldo")
