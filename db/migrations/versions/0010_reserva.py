"""reserva, cobertura e aporte mensal (SPEC-009, ADR 047)

Revision ID: 0010
Revises: 0009

SQL puro (ADR 025).

- `reserva_parametro`: N (meses da meta), gasto essencial e data-alvo (opcional), com vigência.
  Append-only como o fechamento do cartão (ADR 043 item 5): nada é atualizado nem apagado; para
  a mesma `vigente_desde` vale o último gravado (`reserva_parametro_vigente`).
- `reserva_parametro_gravar(...)`: única porta de escrita (SECURITY DEFINER, search_path fixo).
- `reserva_situacao(p_user, p_hoje)`: líquido, imposto acumulado, bruto, meta, nível, falta,
  cobertura e aporte da soma das contas de tipo `reserva`. INVOKER, recebe o `user_id` da sessão
  (INV-13) e a data de hoje (determinismo).
- Helpers puros: `reserva_nivel`, `reserva_cobertura`, `reserva_aporte`, `reserva_meses_ate`.
- Mensagens de erro literais (sem `||`).
"""

from __future__ import annotations

from alembic import op

revision = "0010"
down_revision = "0009"
branch_labels = None
depends_on = None

FUNCOES_LEITURA = (
    "reserva_nivel(numeric, numeric)",
    "reserva_cobertura(numeric, numeric)",
    "reserva_aporte(numeric, integer)",
    "reserva_meses_ate(date, date)",
    "reserva_situacao(bigint, date)",
)
ASSIN_GRAVAR = "reserva_parametro_gravar(bigint, integer, numeric, date, date)"

# Nível: comparações exatas (sem arredondar). Meta ausente ou zero => sem nível.
SQL_NIVEL = """
CREATE FUNCTION reserva_nivel(p_saldo numeric, p_meta numeric) RETURNS text
LANGUAGE sql IMMUTABLE AS $$
    SELECT CASE
        WHEN p_saldo IS NULL OR p_meta IS NULL OR p_meta <= 0 THEN NULL
        WHEN p_saldo * 2 < p_meta THEN 'critica'
        WHEN p_saldo < p_meta THEN 'atencao'
        ELSE 'saudavel'
    END
$$
"""

# Meio-para-cima em 2 casas: floor(x * 100 + 0.5) / 100.
SQL_COBERTURA = """
CREATE FUNCTION reserva_cobertura(p_saldo numeric, p_gasto numeric) RETURNS numeric
LANGUAGE sql IMMUTABLE AS $$
    SELECT CASE
        WHEN p_saldo IS NULL OR p_gasto IS NULL OR p_gasto <= 0 THEN NULL
        ELSE (floor(p_saldo / p_gasto * 100 + 0.5) / 100)::numeric(20, 2)
    END
$$
"""

# Aporte: falta / meses arredondado PARA CIMA em centavos, em aritmética inteira (sem erro de
# divisão decimal). Falta <= 0 => 0,00; meses < 1 vira 1.
SQL_APORTE = """
CREATE FUNCTION reserva_aporte(p_falta numeric, p_meses integer) RETURNS numeric
LANGUAGE sql IMMUTABLE AS $$
    SELECT CASE
        WHEN p_falta IS NULL OR p_meses IS NULL THEN NULL
        WHEN p_falta <= 0 THEN 0.00
        ELSE (
            (((p_falta * 100)::bigint + greatest(p_meses, 1) - 1) / greatest(p_meses, 1))::numeric
            / 100
        )::numeric(14, 2)
    END
$$
"""

# Diferença de meses civis (alvo - hoje); negativa se o alvo é de mês anterior.
SQL_MESES_ATE = """
CREATE FUNCTION reserva_meses_ate(p_hoje date, p_alvo date) RETURNS integer
LANGUAGE sql IMMUTABLE AS $$
    SELECT CASE
        WHEN p_hoje IS NULL OR p_alvo IS NULL THEN NULL
        ELSE ((extract(year FROM p_alvo) - extract(year FROM p_hoje)) * 12
              + extract(month FROM p_alvo) - extract(month FROM p_hoje))::int
    END
$$
"""

SQL_GRAVAR = """
CREATE FUNCTION reserva_parametro_gravar(
    p_user bigint, p_meses integer, p_gasto numeric, p_alvo date, p_desde date
)
RETURNS bigint
LANGUAGE plpgsql SECURITY DEFINER SET search_path = public, pg_temp AS $$
DECLARE
    v_id bigint;
BEGIN
    IF p_meses IS NULL OR p_meses < 1 OR p_meses > 120 THEN
        PERFORM abako_erro('AB422', 'a meta vai de 1 a 120 meses');
    END IF;
    IF p_gasto IS NULL OR p_gasto < 0 OR p_gasto >= 1000000000 OR p_gasto <> round(p_gasto, 2)
    THEN
        PERFORM abako_erro('AB422', 'o gasto essencial é zero ou positivo, com até 2 casas');
    END IF;
    IF p_desde IS NULL OR p_desde < DATE '2000-01-01' THEN
        PERFORM abako_erro('AB422', 'a vigência precisa ser uma data a partir de 2000');
    END IF;
    IF p_alvo IS NOT NULL AND p_alvo < DATE '2000-01-01' THEN
        PERFORM abako_erro('AB422', 'a data-alvo precisa ser uma data a partir de 2000');
    END IF;
    PERFORM 1 FROM usuario u WHERE u.user_id = p_user;
    IF NOT FOUND THEN
        PERFORM abako_erro('AB404', 'usuário não encontrado');
    END IF;
    -- Idempotente: repetir o que já vale para essa vigência devolve o registro existente.
    SELECT v.id INTO v_id FROM reserva_parametro_vigente v
    WHERE v.user_id = p_user AND v.vigente_desde = p_desde
      AND v.meses = p_meses AND v.gasto_essencial = p_gasto
      AND v.data_alvo IS NOT DISTINCT FROM p_alvo;
    IF FOUND THEN
        RETURN v_id;
    END IF;
    INSERT INTO reserva_parametro (user_id, meses, gasto_essencial, data_alvo, vigente_desde)
    VALUES (p_user, p_meses, p_gasto, p_alvo, p_desde)
    RETURNING id INTO v_id;
    RETURN v_id;
END
$$
"""

SQL_SITUACAO = """
CREATE FUNCTION reserva_situacao(p_user bigint, p_hoje date)
RETURNS TABLE (
    contas_reserva integer,
    saldo_liquido numeric,
    imposto_acumulado numeric,
    saldo_bruto numeric,
    meses_meta integer,
    gasto_essencial numeric,
    meta numeric,
    nivel text,
    falta numeric,
    cobertura_meses numeric,
    data_alvo date,
    meses_ate_alvo integer,
    alvo_vencida boolean,
    aporte_mensal numeric,
    config_pendente boolean
)
LANGUAGE plpgsql STABLE AS $$
DECLARE
    v_contas integer;
    v_saldo numeric;
    v_imposto numeric;
    v_meses integer := 3;
    v_gasto numeric;
    v_alvo date;
    v_pendente boolean;
    v_meta numeric;
    v_falta numeric;
    v_dif integer;
    v_vencida boolean := false;
    v_ate integer;
    v_aporte numeric;
BEGIN
    IF p_hoje IS NULL THEN
        RAISE EXCEPTION USING ERRCODE = 'AB422', MESSAGE = 'a data de hoje é obrigatória';
    END IF;
    SELECT count(*)::int,
           COALESCE(sum(saldo_derivado(p_user, c.conta_id, p_hoje)), 0.00)
    INTO v_contas, v_saldo
    FROM conta_versao c
    WHERE c.user_id = p_user AND c.vigente AND NOT c.excluida AND c.tipo = 'reserva';

    SELECT COALESCE(sum(t.imposto), 0.00) INTO v_imposto
    FROM transacao_vigente t
    WHERE t.user_id = p_user AND t.tipo = 'rendimento' AND t.data_transacao <= p_hoje
      AND EXISTS (
          SELECT 1 FROM conta_versao c
          WHERE c.user_id = t.user_id AND c.conta_id = t.conta_id
            AND c.vigente AND NOT c.excluida AND c.tipo = 'reserva');

    SELECT p.meses, p.gasto_essencial, p.data_alvo INTO v_meses, v_gasto, v_alvo
    FROM reserva_parametro_vigente p
    WHERE p.user_id = p_user AND p.vigente_desde <= p_hoje
    ORDER BY p.vigente_desde DESC
    LIMIT 1;
    IF NOT FOUND THEN
        v_meses := 3;  -- padrão do ADR 007 enquanto nada foi informado
        v_gasto := NULL;
        v_alvo := NULL;
    END IF;

    v_pendente := v_gasto IS NULL OR v_gasto <= 0;
    IF NOT v_pendente THEN
        v_meta := (v_meses * v_gasto)::numeric(14, 2);
        v_falta := greatest(v_meta - v_saldo, 0.00);
        IF v_alvo IS NOT NULL THEN
            v_dif := reserva_meses_ate(p_hoje, v_alvo);
            IF v_falta = 0 THEN
                v_aporte := 0.00;
                IF v_dif >= 0 THEN
                    v_ate := greatest(v_dif, 1);
                END IF;
            ELSIF v_dif < 0 THEN
                v_vencida := true;
            ELSE
                v_ate := greatest(v_dif, 1);
                v_aporte := reserva_aporte(v_falta, v_ate);
            END IF;
        END IF;
    END IF;

    RETURN QUERY SELECT
        v_contas,
        v_saldo,
        v_imposto,
        v_saldo + v_imposto,
        v_meses,
        v_gasto,
        v_meta,
        reserva_nivel(v_saldo, v_meta),
        v_falta,
        reserva_cobertura(v_saldo, v_gasto),
        v_alvo,
        v_ate,
        v_vencida,
        v_aporte,
        v_pendente;
END
$$
"""


def upgrade() -> None:
    op.execute(
        """
        CREATE TABLE reserva_parametro (
            id              bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
            user_id         bigint   NOT NULL REFERENCES usuario (user_id),
            meses           smallint NOT NULL CHECK (meses BETWEEN 1 AND 120),
            gasto_essencial numeric(14, 2) NOT NULL CHECK (gasto_essencial >= 0),
            data_alvo       date,
            vigente_desde   date     NOT NULL CHECK (vigente_desde >= DATE '2000-01-01'),
            registrado_em   timestamptz NOT NULL DEFAULT now()
        )
        """
    )
    op.execute(
        "CREATE INDEX reserva_parametro_user_idx ON reserva_parametro "
        "(user_id, vigente_desde, registrado_em)"
    )
    op.execute(
        """
        CREATE VIEW reserva_parametro_vigente WITH (security_invoker = true) AS
        SELECT DISTINCT ON (user_id, vigente_desde)
               id, user_id, meses, gasto_essencial, data_alvo, vigente_desde, registrado_em
        FROM reserva_parametro
        ORDER BY user_id, vigente_desde, registrado_em DESC, id DESC
        """
    )
    op.execute(SQL_NIVEL)
    op.execute(SQL_COBERTURA)
    op.execute(SQL_APORTE)
    op.execute(SQL_MESES_ATE)
    op.execute(SQL_GRAVAR)
    op.execute(SQL_SITUACAO)

    op.execute("GRANT SELECT ON reserva_parametro, reserva_parametro_vigente TO abako_app")
    op.execute("GRANT SELECT ON reserva_parametro, reserva_parametro_vigente TO abako_pipeline")
    for assinatura in (*FUNCOES_LEITURA, ASSIN_GRAVAR):
        op.execute(f"REVOKE ALL ON FUNCTION {assinatura} FROM PUBLIC")
        op.execute(f"GRANT EXECUTE ON FUNCTION {assinatura} TO abako_app")


def downgrade() -> None:
    # Recusa se houver parâmetros: o downgrade apagaria configuração do usuário.
    op.execute(
        """
        DO $$
        BEGIN
            IF EXISTS (SELECT 1 FROM reserva_parametro) THEN
                RAISE EXCEPTION USING MESSAGE =
                    '0010: há parâmetros da reserva que só existem nesta versão; o downgrade '
                    'apagaria dados. Restaure o backup anterior à 0010 (ADR 047).';
            END IF;
        END $$
        """
    )
    op.execute(f"DROP FUNCTION {ASSIN_GRAVAR}")
    for assinatura in reversed(FUNCOES_LEITURA):
        op.execute(f"DROP FUNCTION {assinatura}")
    op.execute("DROP VIEW reserva_parametro_vigente")
    op.execute("DROP TABLE reserva_parametro")
