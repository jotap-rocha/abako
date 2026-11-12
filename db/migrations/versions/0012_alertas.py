"""alertas R1, R2 e R4 derivados na hora (SPEC-011, ADR 049)

Revision ID: 0012
Revises: 0011

SQL puro (ADR 025). Nenhuma tabela nova: o alerta é DERIVADO a cada consulta, sem estado, sem
dispensa e sem histórico. Uma única função de leitura `INVOKER`:

- `alertas(p_user, p_hoje)`: compõe `reserva_situacao` (R1), `r2_situacao` (R2) e `r4_divergencias`
  (R4) e devolve uma linha por alerta, já ordenada por severidade (alta, media, baixa), depois por
  código. Os cortes de nível e o `sobra < 0` continuam nas funções de origem (ADR 047 e 048); aqui
  só se decide o que vira alerta e com que severidade (ADR 049).
- Mensagens são literais, sem valores, nomes ou ids; os números vão em colunas próprias.
- O app executa; o pipeline não tem `EXECUTE`. Escrita nenhuma.
"""

from __future__ import annotations

from alembic import op

revision = "0012"
down_revision = "0011"
branch_labels = None
depends_on = None

ASSINATURA = "alertas(bigint, date)"

# Colunas: identificação (codigo, tipo, severidade, detalhe, mensagem), R1, R2 e R4. Cada ramo do
# UNION preenche só as suas; o resto fica nulo.
SQL_ALERTAS = """
CREATE FUNCTION alertas(p_user bigint, p_hoje date)
RETURNS TABLE (
    codigo text, tipo text, severidade text, detalhe text, mensagem text,
    nivel text, saldo_liquido numeric, meta numeric, falta numeric, cobertura_meses numeric,
    horizonte_dias integer, data_fim date, sobra numeric, disponivel numeric,
    compromissos numeric, sobra_nao_confiavel boolean, vencidas integer,
    pendencias_vencimento integer,
    conta_id bigint, data_snapshot date, valor_snapshot numeric, saldo_derivado numeric,
    divergencia numeric, quantidade integer
)
LANGUAGE plpgsql STABLE SET search_path = public, pg_temp AS $$
#variable_conflict use_column
BEGIN
    IF p_hoje IS NULL THEN
        RAISE EXCEPTION USING ERRCODE = 'AB422', MESSAGE = 'a data de hoje é obrigatória';
    END IF;
    RETURN QUERY
    WITH r AS (SELECT * FROM reserva_situacao(p_user, p_hoje)),
    s AS (SELECT * FROM r2_situacao(p_user, p_hoje)),
    a AS (
        -- R1: crítica = alerta forte; atenção = aviso; saudável = nada. Configuração pendente
        -- (gasto essencial ausente ou zero) não é R1: vira o item de configuração abaixo.
        SELECT 'R1'::text AS codigo,
               CASE r.nivel WHEN 'critica' THEN 'alerta' ELSE 'aviso' END AS tipo,
               CASE r.nivel WHEN 'critica' THEN 'alta' ELSE 'media' END AS severidade,
               CASE r.nivel WHEN 'critica' THEN 'reserva_critica'
                            ELSE 'reserva_atencao' END AS detalhe,
               CASE r.nivel WHEN 'critica' THEN 'a reserva está abaixo de metade da meta'
                            ELSE 'a reserva está abaixo da meta' END AS mensagem,
               r.nivel AS nivel, r.saldo_liquido AS saldo_liquido, r.meta AS meta,
               r.falta AS falta, r.cobertura_meses AS cobertura_meses,
               NULL::integer AS horizonte_dias, NULL::date AS data_fim, NULL::numeric AS sobra,
               NULL::numeric AS disponivel, NULL::numeric AS compromissos,
               NULL::boolean AS sobra_nao_confiavel, NULL::integer AS vencidas,
               NULL::integer AS pendencias_vencimento,
               NULL::bigint AS conta_id, NULL::date AS data_snapshot,
               NULL::numeric AS valor_snapshot, NULL::numeric AS saldo_derivado,
               NULL::numeric AS divergencia, NULL::integer AS quantidade
        FROM r
        WHERE NOT r.config_pendente AND r.nivel IN ('critica', 'atencao')
        UNION ALL
        SELECT 'CONFIG', 'configuracao', 'baixa', 'reserva_gasto_essencial',
               'informe o gasto essencial para calcular a meta da reserva',
               NULL, r.saldo_liquido, NULL, NULL, NULL,
               NULL, NULL, NULL, NULL, NULL, NULL, NULL, NULL,
               NULL, NULL, NULL, NULL, NULL, NULL
        FROM r
        WHERE r.config_pendente
        UNION ALL
        -- R2: sobra < 0 (estrito) é alerta forte; se há cartão com dívida sem vencimento ou
        -- fechamento, a sobra não é confiável (mesmo negativa).
        SELECT 'R2', 'alerta', 'alta', 'sobra_negativa',
               'a sobra do horizonte está negativa',
               NULL, NULL, NULL, NULL, NULL,
               s.horizonte_dias, s.data_fim, s.sobra, s.disponivel, s.compromissos,
               s.pendencias_vencimento > 0, s.vencidas, s.pendencias_vencimento,
               NULL, NULL, NULL, NULL, NULL, NULL
        FROM s
        WHERE s.alerta
        UNION ALL
        SELECT 'R2', 'aviso', 'media', 'sobra_nao_confiavel',
               'a sobra não é confiável: há cartão com dívida sem vencimento ou fechamento',
               NULL, NULL, NULL, NULL, NULL,
               s.horizonte_dias, s.data_fim, s.sobra, s.disponivel, s.compromissos,
               true, s.vencidas, s.pendencias_vencimento,
               NULL, NULL, NULL, NULL, NULL, NULL
        FROM s
        WHERE NOT s.alerta AND s.pendencias_vencimento > 0
        UNION ALL
        SELECT 'R2', 'aviso', 'baixa', 'vencidas',
               'há ocorrências recorrentes vencidas sem vínculo a uma transação',
               NULL, NULL, NULL, NULL, NULL,
               s.horizonte_dias, s.data_fim, s.sobra, s.disponivel, s.compromissos,
               s.pendencias_vencimento > 0, s.vencidas, s.pendencias_vencimento,
               NULL, NULL, NULL, NULL, NULL, NULL
        FROM s
        WHERE s.vencidas > 0
        UNION ALL
        -- R4: por conta vigente, o snapshot divergente mais recente (até hoje) e quantos há.
        -- Cartão = a conta de dívida (snapshot de fatura foi adiado). Nunca corrige nada.
        SELECT 'R4', 'aviso', 'media', 'divergencia_saldo',
               'o saldo derivado da conta diverge do snapshot informado',
               NULL, NULL, NULL, NULL, NULL,
               NULL, NULL, NULL, NULL, NULL, NULL, NULL, NULL,
               d.conta_id, d.data_snapshot, d.valor_snapshot, d.saldo_derivado, d.divergencia,
               d.quantidade
        FROM (
            SELECT x.conta_id, x.data_snapshot, x.valor_snapshot, x.saldo_derivado,
                   x.divergencia,
                   (count(*) OVER (PARTITION BY x.conta_id))::int AS quantidade,
                   row_number() OVER (PARTITION BY x.conta_id
                                      ORDER BY x.data_snapshot DESC) AS ordem
            FROM r4_divergencias(p_user) x
            WHERE x.data_snapshot <= p_hoje
              AND EXISTS (SELECT 1 FROM conta_versao c
                          WHERE c.user_id = p_user AND c.conta_id = x.conta_id
                            AND c.vigente AND NOT c.excluida)
        ) d
        WHERE d.ordem = 1
    )
    SELECT a.codigo, a.tipo, a.severidade, a.detalhe, a.mensagem,
           a.nivel, a.saldo_liquido, a.meta, a.falta, a.cobertura_meses,
           a.horizonte_dias, a.data_fim, a.sobra, a.disponivel, a.compromissos,
           a.sobra_nao_confiavel, a.vencidas, a.pendencias_vencimento,
           a.conta_id, a.data_snapshot, a.valor_snapshot, a.saldo_derivado, a.divergencia,
           a.quantidade
    FROM a
    ORDER BY CASE a.severidade WHEN 'alta' THEN 1 WHEN 'media' THEN 2 ELSE 3 END,
             a.codigo, a.detalhe, a.conta_id;
END
$$
"""


def upgrade() -> None:
    op.execute(SQL_ALERTAS)
    op.execute(f"REVOKE ALL ON FUNCTION {ASSINATURA} FROM PUBLIC")
    op.execute(f"GRANT EXECUTE ON FUNCTION {ASSINATURA} TO abako_app")


def downgrade() -> None:
    # Sem tabelas nem dados: o alerta é derivado, então o downgrade só remove a função.
    op.execute(f"DROP FUNCTION {ASSINATURA}")
