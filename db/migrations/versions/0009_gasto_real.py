"""gasto real e receita de caixa do mês (SPEC-008, ADR 046)

Revision ID: 0009
Revises: 0008

SQL puro (ADR 025). Só leituras derivadas (nada é gravado, nenhuma tabela nova):

- `mes_inicio(p_mes)`: primeiro dia do mês `AAAA-MM`; mês fora do formato é recusado (AB422).
- `gasto_real_itens(p_user, p_mes)`: o que compõe o gasto real. Débito/pix pela data do
  lançamento; compra a crédito por parcela na competência da fatura (`parcela_ativa`, que já
  tira a compra estornada e `pessoa_id IS NULL` deixa terceiros de fora). Débito de conta de
  benefício fica de fora; débito em reserva ou investimento conta (é consumo).
- `gasto_real`, `gasto_real_por_conta`, `receita_caixa`, `receita_beneficio`, `receita_total`.
- Funções INVOKER que recebem o `user_id` da sessão (INV-13). Só o app executa; o pipeline não.
  Mensagens de erro são literais.
"""

from __future__ import annotations

from alembic import op

revision = "0009"
down_revision = "0008"
branch_labels = None
depends_on = None

FUNCOES = (
    "mes_inicio(text)",
    "gasto_real_itens(bigint, text)",
    "gasto_real(bigint, text)",
    "gasto_real_por_conta(bigint, text)",
    "receita_caixa(bigint, text)",
    "receita_beneficio(bigint, text)",
    "receita_total(bigint, text)",
)

SQL_MES_INICIO = """
CREATE FUNCTION mes_inicio(p_mes text) RETURNS date
LANGUAGE plpgsql IMMUTABLE AS $$
BEGIN
    IF p_mes IS NULL OR p_mes !~ '^[2-9][0-9]{3}-(0[1-9]|1[0-2])$' THEN
        RAISE EXCEPTION USING ERRCODE = 'AB422', MESSAGE = 'o mês precisa estar no formato AAAA-MM';
    END IF;
    RETURN to_date(p_mes || '-01', 'YYYY-MM-DD');
END
$$
"""

# Itens do gasto real: valor sempre positivo. `origem` = 'debito' | 'parcela'.
SQL_GASTO_REAL_ITENS = """
CREATE FUNCTION gasto_real_itens(p_user bigint, p_mes text)
RETURNS TABLE (transacao_id bigint, conta_id bigint, origem text, valor numeric)
LANGUAGE plpgsql STABLE AS $$
DECLARE
    v_ini date := mes_inicio(p_mes);
BEGIN
    RETURN QUERY
    SELECT t.transacao_id, t.conta_id, 'debito'::text, -t.valor
    FROM transacao_vigente t
    WHERE t.user_id = p_user AND t.tipo = 'debito'
      AND t.data_transacao >= v_ini
      AND t.data_transacao < (v_ini + interval '1 month')::date
      AND NOT EXISTS (
          SELECT 1 FROM conta_versao c
          WHERE c.user_id = t.user_id AND c.conta_id = t.conta_id
            AND c.vigente AND c.tipo = 'beneficio')
    UNION ALL
    SELECT a.transacao_id, a.conta_id, 'parcela'::text, -a.valor
    FROM parcela_ativa a
    WHERE a.user_id = p_user AND a.competencia = p_mes AND a.pessoa_id IS NULL;
END
$$
"""

SQL_GASTO_REAL = """
CREATE FUNCTION gasto_real(p_user bigint, p_mes text) RETURNS numeric
LANGUAGE sql STABLE AS $$
    SELECT COALESCE(sum(i.valor), 0.00) FROM gasto_real_itens(p_user, p_mes) i
$$
"""

SQL_GASTO_REAL_POR_CONTA = """
CREATE FUNCTION gasto_real_por_conta(p_user bigint, p_mes text)
RETURNS TABLE (conta_id bigint, valor numeric)
LANGUAGE sql STABLE AS $$
    SELECT i.conta_id, sum(i.valor)
    FROM gasto_real_itens(p_user, p_mes) i
    GROUP BY i.conta_id
    ORDER BY i.conta_id
$$
"""


def _sql_receita(nome: str, beneficio: bool) -> str:
    teste = "EXISTS" if beneficio else "NOT EXISTS"
    return f"""
CREATE FUNCTION {nome}(p_user bigint, p_mes text) RETURNS numeric
LANGUAGE plpgsql STABLE AS $$
DECLARE
    v_ini date := mes_inicio(p_mes);
    v_total numeric;
BEGIN
    SELECT COALESCE(sum(t.valor), 0.00) INTO v_total
    FROM transacao_vigente t
    WHERE t.user_id = p_user AND t.tipo = 'receita'
      AND t.data_transacao >= v_ini
      AND t.data_transacao < (v_ini + interval '1 month')::date
      AND {teste} (
          SELECT 1 FROM conta_versao c
          WHERE c.user_id = t.user_id AND c.conta_id = t.conta_id
            AND c.vigente AND c.tipo = 'beneficio');
    RETURN v_total;
END
$$
"""


SQL_RECEITA_TOTAL = """
CREATE FUNCTION receita_total(p_user bigint, p_mes text) RETURNS numeric
LANGUAGE sql STABLE AS $$
    SELECT receita_caixa(p_user, p_mes) + receita_beneficio(p_user, p_mes)
$$
"""


def upgrade() -> None:
    op.execute(SQL_MES_INICIO)
    op.execute(SQL_GASTO_REAL_ITENS)
    op.execute(SQL_GASTO_REAL)
    op.execute(SQL_GASTO_REAL_POR_CONTA)
    op.execute(_sql_receita("receita_caixa", beneficio=False))
    op.execute(_sql_receita("receita_beneficio", beneficio=True))
    op.execute(SQL_RECEITA_TOTAL)
    for assinatura in FUNCOES:
        op.execute(f"REVOKE ALL ON FUNCTION {assinatura} FROM PUBLIC")
        op.execute(f"GRANT EXECUTE ON FUNCTION {assinatura} TO abako_app")


def downgrade() -> None:
    # Só leituras derivadas: sem dado que se perca. A ordem respeita as dependências.
    for assinatura in reversed(FUNCOES):
        op.execute(f"DROP FUNCTION {assinatura}")
