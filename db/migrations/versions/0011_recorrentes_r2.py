"""recorrentes, vínculo, vencimento do cartão e sobra do R2 (SPEC-010, ADR 048)

Revision ID: 0011
Revises: 0010

SQL puro (ADR 025). A regra vive no banco (ADR 015):

- `recorrente`: cadastro versionado como `pessoa` (`versao`, `vigente`, `excluida`); tipo `fixo` ou
  `receita`, valor esperado, dia do mês, conta corrente e período `mes_inicio`..`mes_fim`.
  A ocorrência de cada mês é derivada (nunca gravada); dia 29 a 31 usa o último dia do mês.
- `recorrente_vinculo`: eventos append-only (ocorrência -> transação; transação nula = desvinculou).
  Vale o último evento; só conta (`recorrente_vinculo_efetivo`) se a transação segue vigente, do
  tipo e da conta do recorrente.
- `r2_parametro`: horizonte do R2 em dias (1 a 90) com vigência, append-only; inicial 10.
- `cartao_vencimento`: dia de vencimento por cartão com vigência, append-only, como o fechamento.
- Vigência retroativa: competência anterior à primeira vigência de fechamento ou de vencimento
  usa a PRIMEIRA vigência (nunca some da sobra); sem nenhuma, vira `pendencias_vencimento`.
- R2 conservador no tempo: só abate pagamento de fatura com data <= hoje
  (`alocacao_pago_ate`/`pool_pago_ate`, sem mudar `alocacao_pago`/`pool_pago` do ADR 044) e só
  tira a ocorrência se a transação vinculada tem data <= hoje. Vencidas: até 24 meses atrás.
- Escrita só por funções `SECURITY DEFINER` com `search_path` fixo: `recorrente_gravar`,
  `recorrente_excluir`, `recorrente_vincular`, `recorrente_desvincular`, `r2_parametro_gravar`,
  `vencimento_gravar`. Mensagens de erro literais (sem `||`).
- Leituras `INVOKER` com `p_user` (INV-13) e `p_hoje`: `ocorrencias_do_mes`, `fatura_fechamento`,
  `vencimento_fatura`, `r2_horizonte`, `r2_itens`, `r2_situacao`; helpers `data_no_mes` e
  `meses_entre`. O app executa; o pipeline não tem EXECUTE e não lê o nome do recorrente.
"""

from __future__ import annotations

from alembic import op

revision = "0011"
down_revision = "0010"
branch_labels = None
depends_on = None

FUNCOES_LEITURA = (
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
FUNCOES_ESCRITA = (
    "recorrente_gravar(bigint, bigint, integer, text, text, numeric, integer, bigint, text, text)",
    "recorrente_excluir(bigint, bigint, integer)",
    "recorrente_vincular(bigint, bigint, text, bigint)",
    "recorrente_desvincular(bigint, bigint, text)",
    "r2_parametro_gravar(bigint, integer, date)",
    "vencimento_gravar(bigint, bigint, integer, date)",
)

# ---------------------------------------------------------------------------------------------
# Helpers puros
# ---------------------------------------------------------------------------------------------

# Dia do mês, ou o último dia válido quando ele não existe (mesma regra do ADR 027).
SQL_DATA_NO_MES = """
CREATE FUNCTION data_no_mes(p_dia integer, p_mes date) RETURNS date
LANGUAGE sql IMMUTABLE AS $$
    SELECT s.primeiro + (least(
               p_dia,
               extract(day FROM (s.primeiro + interval '1 month' - interval '1 day'))::int
           ) - 1)
    FROM (SELECT make_date(extract(year FROM p_mes)::int,
                           extract(month FROM p_mes)::int, 1) AS primeiro) s
$$
"""

# Diferença de meses civis (b - a); negativa se b é de mês anterior ao de a.
SQL_MESES_ENTRE = """
CREATE FUNCTION meses_entre(p_a date, p_b date) RETURNS integer
LANGUAGE sql IMMUTABLE AS $$
    SELECT ((extract(year FROM p_b) - extract(year FROM p_a)) * 12
            + extract(month FROM p_b) - extract(month FROM p_a))::int
$$
"""

# ---------------------------------------------------------------------------------------------
# Escrita (SECURITY DEFINER)
# ---------------------------------------------------------------------------------------------

SQL_R2_PARAMETRO_GRAVAR = """
CREATE FUNCTION r2_parametro_gravar(p_user bigint, p_dias integer, p_desde date)
RETURNS bigint
LANGUAGE plpgsql SECURITY DEFINER SET search_path = public, pg_temp AS $$
DECLARE
    v_id bigint;
BEGIN
    IF p_dias IS NULL OR p_dias < 1 OR p_dias > 90 THEN
        PERFORM abako_erro('AB422', 'o horizonte do R2 vai de 1 a 90 dias');
    END IF;
    IF p_desde IS NULL OR p_desde < DATE '2000-01-01' THEN
        PERFORM abako_erro('AB422', 'a vigência precisa ser uma data a partir de 2000');
    END IF;
    IF p_desde > ((now() AT TIME ZONE 'America/Sao_Paulo')::date + interval '5 years')::date THEN
        PERFORM abako_erro('AB422', 'a vigência não pode passar de 5 anos no futuro');
    END IF;
    PERFORM 1 FROM usuario u WHERE u.user_id = p_user;
    IF NOT FOUND THEN
        PERFORM abako_erro('AB404', 'usuário não encontrado');
    END IF;
    -- Idempotente: repetir o que já vale para essa vigência devolve o registro existente.
    SELECT v.id INTO v_id FROM r2_parametro_vigente v
    WHERE v.user_id = p_user AND v.vigente_desde = p_desde AND v.dias = p_dias;
    IF FOUND THEN
        RETURN v_id;
    END IF;
    INSERT INTO r2_parametro (user_id, dias, vigente_desde)
    VALUES (p_user, p_dias, p_desde)
    RETURNING id INTO v_id;
    RETURN v_id;
END
$$
"""

SQL_VENCIMENTO_GRAVAR = """
CREATE FUNCTION vencimento_gravar(
    p_user bigint, p_conta bigint, p_dia integer, p_desde date
)
RETURNS bigint
LANGUAGE plpgsql SECURITY DEFINER SET search_path = public, pg_temp AS $$
DECLARE
    v_id bigint;
BEGIN
    IF p_dia IS NULL OR p_dia < 1 OR p_dia > 31 THEN
        PERFORM abako_erro('AB422', 'o dia de vencimento vai de 1 a 31');
    END IF;
    IF p_desde IS NULL OR p_desde < DATE '2000-01-01' THEN
        PERFORM abako_erro('AB422', 'a vigência precisa ser uma data a partir de 2000');
    END IF;
    IF p_desde > ((now() AT TIME ZONE 'America/Sao_Paulo')::date + interval '5 years')::date THEN
        PERFORM abako_erro('AB422', 'a vigência não pode passar de 5 anos no futuro');
    END IF;
    PERFORM 1 FROM conta_versao c
    WHERE c.user_id = p_user AND c.conta_id = p_conta AND c.vigente AND NOT c.excluida
      AND c.tipo = 'divida'
    FOR SHARE;
    IF NOT FOUND THEN
        PERFORM abako_erro('AB404', 'cartão não encontrado');
    END IF;
    SELECT v.id INTO v_id FROM vencimento_vigente v
    WHERE v.user_id = p_user AND v.conta_id = p_conta AND v.vigente_desde = p_desde
      AND v.dia = p_dia;
    IF FOUND THEN
        RETURN v_id;
    END IF;
    INSERT INTO cartao_vencimento (user_id, conta_id, dia, vigente_desde)
    VALUES (p_user, p_conta, p_dia, p_desde)
    RETURNING id INTO v_id;
    RETURN v_id;
END
$$
"""

SQL_RECORRENTE_GRAVAR = """
CREATE FUNCTION recorrente_gravar(
    p_user bigint, p_recorrente bigint, p_versao integer, p_nome text, p_tipo text,
    p_valor numeric, p_dia integer, p_conta bigint, p_inicio text, p_fim text
)
RETURNS TABLE (recorrente_id bigint, versao integer)
LANGUAGE plpgsql SECURITY DEFINER SET search_path = public, pg_temp AS $$
#variable_conflict use_column
DECLARE
    v_nome text := btrim(coalesce(p_nome, ''));
    v_atual recorrente%ROWTYPE;
    v_id bigint;
    v_versao integer;
    v_ini date;
    v_fim date;
    v_ctipo text;
BEGIN
    IF v_nome = '' OR length(v_nome) > 80 THEN
        PERFORM abako_erro('AB422', 'o nome precisa ter de 1 a 80 caracteres');
    END IF;
    IF p_tipo IS NULL OR p_tipo NOT IN ('fixo', 'receita') THEN
        PERFORM abako_erro('AB422', 'o tipo do recorrente é fixo ou receita');
    END IF;
    IF p_valor IS NULL OR p_valor <= 0 OR p_valor >= 1000000000000
       OR p_valor <> round(p_valor, 2) THEN
        PERFORM abako_erro('AB422', 'o valor esperado é positivo, com até 2 casas');
    END IF;
    IF p_dia IS NULL OR p_dia < 1 OR p_dia > 31 THEN
        PERFORM abako_erro('AB422', 'o dia do mês vai de 1 a 31');
    END IF;
    IF p_inicio IS NULL THEN
        PERFORM abako_erro('AB422', 'o mês de início é obrigatório');
    END IF;
    v_ini := mes_inicio(p_inicio);
    IF p_fim IS NOT NULL THEN
        v_fim := mes_inicio(p_fim);
        IF v_fim < v_ini THEN
            PERFORM abako_erro('AB422', 'o mês final não pode ser anterior ao inicial');
        END IF;
    END IF;
    PERFORM 1 FROM usuario u WHERE u.user_id = p_user;
    IF NOT FOUND THEN
        PERFORM abako_erro('AB404', 'usuário não encontrado');
    END IF;
    SELECT c.tipo INTO v_ctipo FROM conta_versao c
    WHERE c.user_id = p_user AND c.conta_id = p_conta AND c.vigente AND NOT c.excluida
    FOR SHARE;
    IF NOT FOUND THEN
        PERFORM abako_erro('AB404', 'conta não encontrada');
    END IF;
    IF v_ctipo <> 'corrente' THEN
        PERFORM abako_erro('AB422', 'o recorrente só pode ficar em conta corrente');
    END IF;

    IF p_recorrente IS NULL THEN
        v_id := nextval('recorrente_id_seq');
        v_versao := 1;
    ELSE
        IF p_versao IS NULL THEN
            PERFORM abako_erro('AB422', 'editar o recorrente exige a versão lida');
        END IF;
        SELECT * INTO v_atual FROM recorrente r
        WHERE r.user_id = p_user AND r.recorrente_id = p_recorrente AND r.vigente
          AND NOT r.excluida
        FOR UPDATE;
        IF NOT FOUND THEN
            PERFORM abako_erro('AB404', 'recorrente não encontrado');
        END IF;
        IF v_atual.versao IS DISTINCT FROM p_versao THEN
            PERFORM abako_erro('AB409', 'o recorrente mudou desde a última leitura');
        END IF;
        IF (v_atual.tipo <> p_tipo OR v_atual.conta_id <> p_conta)
           AND EXISTS (SELECT 1 FROM recorrente_vinculo x
                       WHERE x.user_id = p_user AND x.recorrente_id = p_recorrente) THEN
            PERFORM abako_erro('AB422',
                'tipo e conta do recorrente não mudam depois de haver vínculos');
        END IF;
        IF EXISTS (SELECT 1 FROM recorrente_vinculo_vigente x
                   WHERE x.user_id = p_user AND x.recorrente_id = p_recorrente
                     AND x.transacao_id IS NOT NULL
                     AND (x.mes < v_ini OR (v_fim IS NOT NULL AND x.mes > v_fim))) THEN
            PERFORM abako_erro('AB422', 'há vínculos fora do novo período do recorrente');
        END IF;
        UPDATE recorrente r SET vigente = false WHERE r.id = v_atual.id;
        v_id := p_recorrente;
        v_versao := v_atual.versao + 1;
    END IF;
    BEGIN
        INSERT INTO recorrente (user_id, recorrente_id, versao, nome, tipo, valor, dia,
                                conta_id, mes_inicio, mes_fim)
        VALUES (p_user, v_id, v_versao, v_nome, p_tipo, p_valor, p_dia, p_conta, v_ini, v_fim);
    EXCEPTION WHEN unique_violation THEN
        PERFORM abako_erro('AB410', 'já existe um recorrente com esse nome');
    END;
    RETURN QUERY SELECT v_id, v_versao;
END
$$
"""

SQL_RECORRENTE_EXCLUIR = """
CREATE FUNCTION recorrente_excluir(p_user bigint, p_recorrente bigint, p_versao integer)
RETURNS integer
LANGUAGE plpgsql SECURITY DEFINER SET search_path = public, pg_temp AS $$
DECLARE
    v_atual recorrente%ROWTYPE;
BEGIN
    SELECT * INTO v_atual FROM recorrente r
    WHERE r.user_id = p_user AND r.recorrente_id = p_recorrente AND r.vigente AND NOT r.excluida
    FOR UPDATE;
    IF NOT FOUND THEN
        PERFORM abako_erro('AB404', 'recorrente não encontrado');
    END IF;
    IF v_atual.versao IS DISTINCT FROM p_versao THEN
        PERFORM abako_erro('AB409', 'o recorrente mudou desde a última leitura');
    END IF;
    UPDATE recorrente r SET vigente = false WHERE r.id = v_atual.id;
    INSERT INTO recorrente (user_id, recorrente_id, versao, vigente, excluida, nome, tipo, valor,
                            dia, conta_id, mes_inicio, mes_fim)
    VALUES (p_user, p_recorrente, p_versao + 1, true, true, v_atual.nome, v_atual.tipo,
            v_atual.valor, v_atual.dia, v_atual.conta_id, v_atual.mes_inicio, v_atual.mes_fim);
    RETURN p_versao + 1;
END
$$
"""

SQL_RECORRENTE_VINCULAR = """
CREATE FUNCTION recorrente_vincular(
    p_user bigint, p_recorrente bigint, p_mes text, p_transacao bigint
)
RETURNS bigint
LANGUAGE plpgsql SECURITY DEFINER SET search_path = public, pg_temp AS $$
DECLARE
    v_mes date;
    v_r recorrente%ROWTYPE;
    v_ttipo text;
    v_esperado text;
    v_tconta bigint;
    v_atual bigint;
    v_id bigint;
BEGIN
    v_mes := mes_inicio(p_mes);
    SELECT * INTO v_r FROM recorrente r
    WHERE r.user_id = p_user AND r.recorrente_id = p_recorrente AND r.vigente AND NOT r.excluida
    FOR SHARE;
    IF NOT FOUND THEN
        PERFORM abako_erro('AB404', 'recorrente não encontrado');
    END IF;
    IF v_mes < v_r.mes_inicio OR (v_r.mes_fim IS NOT NULL AND v_mes > v_r.mes_fim) THEN
        PERFORM abako_erro('AB422', 'o mês está fora do período do recorrente');
    END IF;
    PERFORM pg_advisory_xact_lock(hashtextextended(p_user::text, 11));
    SELECT t.tipo, t.conta_id INTO v_ttipo, v_tconta FROM transacao_vigente t
    WHERE t.user_id = p_user AND t.transacao_id = p_transacao
    LIMIT 1;
    IF NOT FOUND THEN
        PERFORM abako_erro('AB404', 'transação não encontrada');
    END IF;
    v_esperado := CASE v_r.tipo WHEN 'fixo' THEN 'debito' ELSE 'receita' END;
    IF v_tconta <> v_r.conta_id OR v_ttipo <> v_esperado THEN
        PERFORM abako_erro('AB422', 'a transação não é do tipo e da conta do recorrente');
    END IF;
    SELECT x.transacao_id INTO v_atual FROM recorrente_vinculo_efetivo x
    WHERE x.user_id = p_user AND x.recorrente_id = p_recorrente AND x.mes = v_mes;
    IF FOUND THEN
        IF v_atual <> p_transacao THEN
            PERFORM abako_erro('AB410', 'a ocorrência já está vinculada a outra transação');
        END IF;
        SELECT x.id INTO v_id FROM recorrente_vinculo_vigente x
        WHERE x.user_id = p_user AND x.recorrente_id = p_recorrente AND x.mes = v_mes;
        RETURN v_id;
    END IF;
    PERFORM 1 FROM recorrente_vinculo_vigente x
    WHERE x.user_id = p_user AND x.transacao_id = p_transacao
      AND NOT (x.recorrente_id = p_recorrente AND x.mes = v_mes);
    IF FOUND THEN
        PERFORM abako_erro('AB410', 'a transação já está vinculada a outra ocorrência');
    END IF;
    INSERT INTO recorrente_vinculo (user_id, recorrente_id, mes, transacao_id)
    VALUES (p_user, p_recorrente, v_mes, p_transacao)
    RETURNING id INTO v_id;
    RETURN v_id;
END
$$
"""

SQL_RECORRENTE_DESVINCULAR = """
CREATE FUNCTION recorrente_desvincular(p_user bigint, p_recorrente bigint, p_mes text)
RETURNS bigint
LANGUAGE plpgsql SECURITY DEFINER SET search_path = public, pg_temp AS $$
DECLARE
    v_mes date;
    v_id bigint;
BEGIN
    v_mes := mes_inicio(p_mes);
    PERFORM 1 FROM recorrente r
    WHERE r.user_id = p_user AND r.recorrente_id = p_recorrente AND r.vigente AND NOT r.excluida
    FOR SHARE;
    IF NOT FOUND THEN
        PERFORM abako_erro('AB404', 'recorrente não encontrado');
    END IF;
    PERFORM pg_advisory_xact_lock(hashtextextended(p_user::text, 11));
    PERFORM 1 FROM recorrente_vinculo_vigente x
    WHERE x.user_id = p_user AND x.recorrente_id = p_recorrente AND x.mes = v_mes
      AND x.transacao_id IS NOT NULL;
    IF NOT FOUND THEN
        PERFORM abako_erro('AB404', 'a ocorrência não está vinculada');
    END IF;
    INSERT INTO recorrente_vinculo (user_id, recorrente_id, mes, transacao_id)
    VALUES (p_user, p_recorrente, v_mes, NULL)
    RETURNING id INTO v_id;
    RETURN v_id;
END
$$
"""

# ---------------------------------------------------------------------------------------------
# Leituras (INVOKER)
# ---------------------------------------------------------------------------------------------

SQL_OCORRENCIAS = """
CREATE FUNCTION ocorrencias_do_mes(p_user bigint, p_mes text)
RETURNS TABLE (
    recorrente_id bigint, nome text, tipo text, conta_id bigint, mes text, data date,
    valor_esperado numeric, valor numeric, transacao_id bigint, vinculada boolean
)
LANGUAGE sql STABLE AS $$
    SELECT r.recorrente_id, r.nome, r.tipo, r.conta_id, to_char(m.mes::timestamp, 'YYYY-MM'),
           data_no_mes(r.dia::int, m.mes), r.valor, COALESCE(e.valor, r.valor),
           e.transacao_id, e.transacao_id IS NOT NULL
    FROM (SELECT mes_inicio(p_mes) AS mes) m
    JOIN recorrente_vigente r
      ON r.user_id = p_user AND r.mes_inicio <= m.mes
     AND (r.mes_fim IS NULL OR m.mes <= r.mes_fim)
    LEFT JOIN recorrente_vinculo_efetivo e
      ON e.user_id = r.user_id AND e.recorrente_id = r.recorrente_id AND e.mes = m.mes
    ORDER BY 6, 1
$$
"""

# Fechamento efetivo da competência: dia vigente no último dia do mês dela; antes da primeira
# vigência cadastrada vale a primeira (retroativo; não reescreve compras já feitas).
SQL_FATURA_FECHAMENTO = """
CREATE FUNCTION fatura_fechamento(p_user bigint, p_conta bigint, p_competencia text)
RETURNS date
LANGUAGE sql STABLE AS $$
    SELECT data_no_mes(f.dia::int, m.mes)
    FROM (SELECT mes_inicio(p_competencia) AS mes) m
    JOIN LATERAL (
        SELECT v.dia FROM fechamento_vigente v
        WHERE v.user_id = p_user AND v.conta_id = p_conta
        ORDER BY (v.vigente_desde > (m.mes + interval '1 month' - interval '1 day')::date),
                 CASE WHEN v.vigente_desde <= (m.mes + interval '1 month' - interval '1 day')::date
                      THEN v.vigente_desde END DESC,
                 v.vigente_desde ASC
        LIMIT 1
    ) f ON true
$$
"""

# Vence no mês M se vencimento > fechamento (dias vigentes no último dia de M); senão em M+1.
# Sem fechamento ou sem vencimento cadastrados, devolve nulo.
SQL_VENCIMENTO_FATURA = """
CREATE FUNCTION vencimento_fatura(p_user bigint, p_conta bigint, p_competencia text)
RETURNS date
LANGUAGE sql STABLE AS $$
    SELECT data_no_mes(
               v.dia::int,
               (m.mes + CASE WHEN v.dia > f.dia THEN interval '0 month'
                             ELSE interval '1 month' END)::date)
    FROM (SELECT mes_inicio(p_competencia) AS mes) m
    JOIN LATERAL (
        SELECT x.dia FROM fechamento_vigente x
        WHERE x.user_id = p_user AND x.conta_id = p_conta
        ORDER BY (x.vigente_desde > (m.mes + interval '1 month' - interval '1 day')::date),
                 CASE WHEN x.vigente_desde <= (m.mes + interval '1 month' - interval '1 day')::date
                      THEN x.vigente_desde END DESC,
                 x.vigente_desde ASC
        LIMIT 1
    ) f ON true
    JOIN LATERAL (
        SELECT y.dia FROM vencimento_vigente y
        WHERE y.user_id = p_user AND y.conta_id = p_conta
        ORDER BY (y.vigente_desde > (m.mes + interval '1 month' - interval '1 day')::date),
                 CASE WHEN y.vigente_desde <= (m.mes + interval '1 month' - interval '1 day')::date
                      THEN y.vigente_desde END DESC,
                 y.vigente_desde ASC
        LIMIT 1
    ) v ON true
$$
"""

# Variantes do ADR 044 só para o R2: pagamento com data > hoje ainda não saiu da conta, então não
# abate. `pool_pago`/`alocacao_pago` (públicas, ADR 044) não mudam. O crédito de estorno sempre
# desconta (lado conservador: menos pago).
SQL_POOL_PAGO_ATE = """
CREATE FUNCTION pool_pago_ate(p_user bigint, p_conta bigint, p_hoje date)
RETURNS numeric
LANGUAGE sql STABLE AS $$
    SELECT COALESCE((SELECT sum(t.valor) FROM transacao_vigente t
                     WHERE t.user_id = p_user AND t.conta_id = p_conta
                       AND t.tipo = 'transferencia' AND t.perna = 2
                       AND t.data_transacao <= p_hoje), 0)
         - COALESCE((SELECT sum(e.estorno_credito) FROM transacao_vigente e
                     WHERE e.user_id = p_user AND e.conta_id = p_conta
                       AND e.tipo = 'estorno'), 0)
$$
"""

SQL_ALOCACAO_PAGO_ATE = """
CREATE FUNCTION alocacao_pago_ate(p_user bigint, p_conta bigint, p_hoje date)
RETURNS TABLE (
    transacao_id bigint, parcela integer, competencia text, data_compra date,
    valor numeric, alocado numeric
)
LANGUAGE sql STABLE AS $$
    WITH p AS (
        SELECT a.transacao_id, a.parcela::int AS parcela, a.competencia,
               a.data_transacao, -a.valor AS valor
        FROM parcela_ativa a
        WHERE a.user_id = p_user AND a.conta_id = p_conta
    ),
    o AS (
        SELECT p.*,
               COALESCE(sum(p.valor) OVER (
                   ORDER BY p.competencia, p.data_transacao, p.parcela, p.transacao_id
                   ROWS BETWEEN UNBOUNDED PRECEDING AND 1 PRECEDING), 0) AS antes
        FROM p
    )
    SELECT o.transacao_id, o.parcela, o.competencia, o.data_transacao, o.valor,
           greatest(0, least(o.valor, pool_pago_ate(p_user, p_conta, p_hoje) - o.antes))
    FROM o
    ORDER BY o.competencia, o.data_transacao, o.parcela, o.transacao_id
$$
"""

SQL_R2_HORIZONTE = """
CREATE FUNCTION r2_horizonte(p_user bigint, p_hoje date) RETURNS integer
LANGUAGE sql STABLE AS $$
    SELECT COALESCE(
        (SELECT p.dias::int FROM r2_parametro_vigente p
         WHERE p.user_id = p_user AND p.vigente_desde <= p_hoje
         ORDER BY p.vigente_desde DESC
         LIMIT 1),
        10)
$$
"""

# Itens do R2. grupo: receita e fixo (pendentes em [hoje, hoje + horizonte]), fatura (própria,
# descontado o pago alocado, vencimento no horizonte) e vencida (não vinculada com data < hoje;
# lista à parte, fora da sobra). Terceiros nunca entram (INV-18).
SQL_R2_ITENS = """
CREATE FUNCTION r2_itens(p_user bigint, p_hoje date)
RETURNS TABLE (
    grupo text, tipo text, recorrente_id bigint, conta_id bigint, competencia text,
    data date, valor numeric, bruto numeric, pago numeric, parcial boolean
)
LANGUAGE plpgsql STABLE AS $$
#variable_conflict use_column
DECLARE
    v_fim date;
    v_lim date;
    v_m0 date;
    v_piso date;
    v_pm date;
BEGIN
    IF p_hoje IS NULL THEN
        RAISE EXCEPTION USING ERRCODE = 'AB422', MESSAGE = 'a data de hoje é obrigatória';
    END IF;
    v_piso := (p_hoje - interval '24 months')::date;
    v_pm := make_date(extract(year FROM v_piso)::int, extract(month FROM v_piso)::int, 1);
    v_fim := p_hoje + r2_horizonte(p_user, p_hoje);
    v_lim := make_date(extract(year FROM v_fim)::int, extract(month FROM v_fim)::int, 1);
    v_m0 := (make_date(extract(year FROM p_hoje)::int, extract(month FROM p_hoje)::int, 1)
             - interval '1 month')::date;
    RETURN QUERY
    WITH oc AS (
        SELECT r.recorrente_id AS rid, r.tipo AS rtipo, r.conta_id AS rconta, r.valor AS rvalor,
               data_no_mes(r.dia::int, g.mes) AS dt,
               CASE WHEN e.data_transacao <= p_hoje THEN e.transacao_id END AS tid
        FROM recorrente_vigente r
        JOIN conta_versao c
          ON c.user_id = r.user_id AND c.conta_id = r.conta_id AND c.vigente AND NOT c.excluida
         AND c.tipo = 'corrente'
        CROSS JOIN LATERAL (
            SELECT (greatest(r.mes_inicio, v_pm) + make_interval(months => k))::date AS mes
            FROM generate_series(
                0, meses_entre(greatest(r.mes_inicio, v_pm),
                               least(COALESCE(r.mes_fim, v_lim), v_lim))) AS s(k)
        ) g
        LEFT JOIN recorrente_vinculo_efetivo e
          ON e.user_id = r.user_id AND e.recorrente_id = r.recorrente_id AND e.mes = g.mes
        WHERE r.user_id = p_user
    ),
    mf AS (
        SELECT c.conta_id AS cid, to_char(g.mes::timestamp, 'YYYY-MM') AS comp
        FROM conta_versao c
        CROSS JOIN LATERAL (
            SELECT (v_m0 + make_interval(months => k))::date AS mes
            FROM generate_series(0, meses_entre(v_m0, v_lim)) AS s(k)
        ) g
        WHERE c.user_id = p_user AND c.vigente AND NOT c.excluida AND c.tipo = 'divida'
    ),
    fx AS (
        SELECT m.cid, m.comp, vencimento_fatura(p_user, m.cid, m.comp) AS venc
        FROM mf m
    )
    SELECT 'vencida'::text, oc.rtipo, oc.rid, oc.rconta, NULL::text, oc.dt, oc.rvalor,
           NULL::numeric, NULL::numeric, NULL::boolean
    FROM oc
    WHERE oc.tid IS NULL AND oc.dt < p_hoje AND oc.dt >= v_piso
    UNION ALL
    SELECT oc.rtipo, oc.rtipo, oc.rid, oc.rconta, NULL::text, oc.dt, oc.rvalor,
           NULL::numeric, NULL::numeric, NULL::boolean
    FROM oc
    WHERE oc.tid IS NULL AND oc.dt BETWEEN p_hoje AND v_fim
    UNION ALL
    SELECT 'fatura'::text, NULL::text, NULL::bigint, x.cid, x.comp, x.venc,
           greatest(b.propria - q.pago, 0.00), b.propria, q.pago,
           fatura_fechamento(p_user, x.cid, x.comp) > p_hoje
    FROM fx x
    CROSS JOIN LATERAL (
        SELECT s.propria FROM fatura_resumo(p_user, x.cid, x.comp) s
    ) b
    CROSS JOIN LATERAL (
        SELECT COALESCE(sum(a.alocado), 0.00) AS pago
        FROM alocacao_pago_ate(p_user, x.cid, p_hoje) a
        JOIN parcela_ativa pa
          ON pa.user_id = p_user AND pa.transacao_id = a.transacao_id AND pa.parcela = a.parcela
        WHERE a.competencia = x.comp AND pa.pessoa_id IS NULL
    ) q
    WHERE x.venc BETWEEN p_hoje AND v_fim
    ORDER BY 1, 6, 3, 4;
END
$$
"""

SQL_R2_SITUACAO = """
CREATE FUNCTION r2_situacao(p_user bigint, p_hoje date)
RETURNS TABLE (
    horizonte_dias integer, data_fim date, saldos_correntes numeric, receitas_pendentes numeric,
    disponivel numeric, fixos_pendentes numeric, faturas_proprias numeric, compromissos numeric,
    sobra numeric, alerta boolean, vencidas integer, pendencias_vencimento integer
)
LANGUAGE plpgsql STABLE AS $$
#variable_conflict use_column
DECLARE
    v_h integer;
    v_fim date;
    v_saldo numeric;
    v_rec numeric;
    v_fix numeric;
    v_fat numeric;
    v_venc integer;
    v_pend integer;
BEGIN
    IF p_hoje IS NULL THEN
        RAISE EXCEPTION USING ERRCODE = 'AB422', MESSAGE = 'a data de hoje é obrigatória';
    END IF;
    v_h := r2_horizonte(p_user, p_hoje);
    v_fim := p_hoje + v_h;
    SELECT COALESCE(sum(saldo_derivado(p_user, c.conta_id, p_hoje)), 0.00) INTO v_saldo
    FROM conta_versao c
    WHERE c.user_id = p_user AND c.vigente AND NOT c.excluida AND c.tipo = 'corrente';
    SELECT COALESCE(sum(i.valor) FILTER (WHERE i.grupo = 'receita'), 0.00),
           COALESCE(sum(i.valor) FILTER (WHERE i.grupo = 'fixo'), 0.00),
           COALESCE(sum(i.valor) FILTER (WHERE i.grupo = 'fatura'), 0.00),
           (count(*) FILTER (WHERE i.grupo = 'vencida'))::int
    INTO v_rec, v_fix, v_fat, v_venc
    FROM r2_itens(p_user, p_hoje) i;
    SELECT count(*)::int INTO v_pend
    FROM conta_versao c
    WHERE c.user_id = p_user AND c.vigente AND NOT c.excluida AND c.tipo = 'divida'
      AND saldo_derivado(p_user, c.conta_id, p_hoje) < 0
      AND (NOT EXISTS (
               SELECT 1 FROM vencimento_vigente v
               WHERE v.user_id = p_user AND v.conta_id = c.conta_id)
           OR NOT EXISTS (
               SELECT 1 FROM fechamento_vigente f
               WHERE f.user_id = p_user AND f.conta_id = c.conta_id));
    RETURN QUERY SELECT
        v_h,
        v_fim,
        v_saldo,
        v_rec,
        v_saldo + v_rec,
        v_fix,
        v_fat,
        v_fix + v_fat,
        (v_saldo + v_rec) - (v_fix + v_fat),
        ((v_saldo + v_rec) - (v_fix + v_fat)) < 0,
        v_venc,
        v_pend;
END
$$
"""

SQLS_FUNCOES = (
    SQL_DATA_NO_MES,
    SQL_MESES_ENTRE,
    SQL_R2_PARAMETRO_GRAVAR,
    SQL_VENCIMENTO_GRAVAR,
    SQL_RECORRENTE_GRAVAR,
    SQL_RECORRENTE_EXCLUIR,
    SQL_RECORRENTE_VINCULAR,
    SQL_RECORRENTE_DESVINCULAR,
    SQL_OCORRENCIAS,
    SQL_FATURA_FECHAMENTO,
    SQL_VENCIMENTO_FATURA,
    SQL_R2_HORIZONTE,
    SQL_POOL_PAGO_ATE,
    SQL_ALOCACAO_PAGO_ATE,
    SQL_R2_ITENS,
    SQL_R2_SITUACAO,
)


def upgrade() -> None:
    # ---------- recorrente (versionado como pessoa) ----------
    op.execute("CREATE SEQUENCE recorrente_id_seq")
    op.execute(
        """
        CREATE TABLE recorrente (
            id            bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
            user_id       bigint   NOT NULL REFERENCES usuario (user_id),
            recorrente_id bigint   NOT NULL DEFAULT nextval('recorrente_id_seq'),
            versao        integer  NOT NULL DEFAULT 1 CHECK (versao >= 1),
            vigente       boolean  NOT NULL DEFAULT true,
            excluida      boolean  NOT NULL DEFAULT false,
            nome          text     NOT NULL CHECK (btrim(nome) <> '' AND length(nome) <= 80),
            tipo          text     NOT NULL CHECK (tipo IN ('fixo', 'receita')),
            valor         numeric(14, 2) NOT NULL CHECK (valor > 0),
            dia           smallint NOT NULL CHECK (dia BETWEEN 1 AND 31),
            conta_id      bigint   NOT NULL,
            mes_inicio    date     NOT NULL
                CHECK (mes_inicio >= DATE '2000-01-01' AND extract(day FROM mes_inicio) = 1),
            mes_fim       date CHECK (mes_fim IS NULL OR extract(day FROM mes_fim) = 1),
            criado_em     timestamptz NOT NULL DEFAULT now(),
            UNIQUE (user_id, recorrente_id, versao),
            CHECK (mes_fim IS NULL OR mes_fim >= mes_inicio)
        )
        """
    )
    op.execute(
        "CREATE UNIQUE INDEX recorrente_vigente_uq ON recorrente (user_id, recorrente_id) "
        "WHERE vigente"
    )
    op.execute(
        "CREATE UNIQUE INDEX recorrente_nome_uq ON recorrente (user_id, lower(nome)) "
        "WHERE vigente AND NOT excluida"
    )
    op.execute(
        """
        CREATE VIEW recorrente_vigente WITH (security_invoker = true) AS
        SELECT id, user_id, recorrente_id, versao, nome, tipo, valor, dia, conta_id,
               mes_inicio, mes_fim, criado_em
        FROM recorrente
        WHERE vigente AND NOT excluida
        """
    )

    # ---------- vínculo (eventos append-only) ----------
    op.execute(
        """
        CREATE TABLE recorrente_vinculo (
            id            bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
            user_id       bigint NOT NULL REFERENCES usuario (user_id),
            recorrente_id bigint NOT NULL,
            mes           date   NOT NULL CHECK (extract(day FROM mes) = 1),
            transacao_id  bigint,
            registrado_em timestamptz NOT NULL DEFAULT now()
        )
        """
    )
    op.execute(
        "CREATE INDEX recorrente_vinculo_ocorrencia_idx ON recorrente_vinculo "
        "(user_id, recorrente_id, mes, id)"
    )
    op.execute(
        "CREATE INDEX recorrente_vinculo_transacao_idx ON recorrente_vinculo "
        "(user_id, transacao_id) WHERE transacao_id IS NOT NULL"
    )
    op.execute(
        """
        CREATE VIEW recorrente_vinculo_vigente WITH (security_invoker = true) AS
        SELECT DISTINCT ON (user_id, recorrente_id, mes)
               id, user_id, recorrente_id, mes, transacao_id, registrado_em
        FROM recorrente_vinculo
        ORDER BY user_id, recorrente_id, mes, id DESC
        """
    )
    op.execute(
        """
        CREATE VIEW recorrente_vinculo_efetivo WITH (security_invoker = true) AS
        SELECT v.user_id, v.recorrente_id, v.mes, v.transacao_id, abs(t.valor) AS valor,
               t.data_transacao
        FROM recorrente_vinculo_vigente v
        JOIN recorrente_vigente r
          ON r.user_id = v.user_id AND r.recorrente_id = v.recorrente_id
        JOIN transacao_vigente t
          ON t.user_id = v.user_id AND t.transacao_id = v.transacao_id
         AND t.conta_id = r.conta_id
         AND t.tipo = CASE r.tipo WHEN 'fixo' THEN 'debito' ELSE 'receita' END
        WHERE v.transacao_id IS NOT NULL
        """
    )

    # ---------- horizonte do R2 e vencimento do cartão (vigência append-only) ----------
    op.execute(
        """
        CREATE TABLE r2_parametro (
            id            bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
            user_id       bigint   NOT NULL REFERENCES usuario (user_id),
            dias          smallint NOT NULL CHECK (dias BETWEEN 1 AND 90),
            vigente_desde date     NOT NULL CHECK (vigente_desde >= DATE '2000-01-01'),
            registrado_em timestamptz NOT NULL DEFAULT now()
        )
        """
    )
    op.execute(
        "CREATE INDEX r2_parametro_user_idx ON r2_parametro (user_id, vigente_desde, registrado_em)"
    )
    op.execute(
        """
        CREATE VIEW r2_parametro_vigente WITH (security_invoker = true) AS
        SELECT DISTINCT ON (user_id, vigente_desde)
               id, user_id, dias, vigente_desde, registrado_em
        FROM r2_parametro
        ORDER BY user_id, vigente_desde, registrado_em DESC, id DESC
        """
    )
    op.execute(
        """
        CREATE TABLE cartao_vencimento (
            id            bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
            user_id       bigint   NOT NULL REFERENCES usuario (user_id),
            conta_id      bigint   NOT NULL,
            dia           smallint NOT NULL CHECK (dia BETWEEN 1 AND 31),
            vigente_desde date     NOT NULL CHECK (vigente_desde >= DATE '2000-01-01'),
            registrado_em timestamptz NOT NULL DEFAULT now()
        )
        """
    )
    op.execute(
        "CREATE INDEX cartao_vencimento_conta_idx ON cartao_vencimento "
        "(user_id, conta_id, vigente_desde, registrado_em)"
    )
    op.execute(
        """
        CREATE VIEW vencimento_vigente WITH (security_invoker = true) AS
        SELECT DISTINCT ON (user_id, conta_id, vigente_desde)
               id, user_id, conta_id, dia, vigente_desde, registrado_em
        FROM cartao_vencimento
        ORDER BY user_id, conta_id, vigente_desde, registrado_em DESC, id DESC
        """
    )

    for sql in SQLS_FUNCOES:
        op.execute(sql)

    # ---------- papéis ----------
    op.execute(
        "GRANT SELECT ON recorrente, recorrente_vigente, recorrente_vinculo, "
        "recorrente_vinculo_vigente, recorrente_vinculo_efetivo, r2_parametro, "
        "r2_parametro_vigente, cartao_vencimento, vencimento_vigente TO abako_app"
    )
    # O pipeline só lê a configuração (horizonte, vencimento). Recorrente e vínculo (nome, valor,
    # dia, conta) ficam fora até a SPEC-014 definir o que o analítico precisa (ADR 048 item 12).
    op.execute(
        "GRANT SELECT ON r2_parametro, r2_parametro_vigente, cartao_vencimento, "
        "vencimento_vigente TO abako_pipeline"
    )
    for assinatura in (*FUNCOES_LEITURA, *FUNCOES_ESCRITA):
        op.execute(f"REVOKE ALL ON FUNCTION {assinatura} FROM PUBLIC")
        op.execute(f"GRANT EXECUTE ON FUNCTION {assinatura} TO abako_app")


def downgrade() -> None:
    # Recusa se houver dados: o downgrade apagaria configuração e histórico do usuário.
    op.execute(
        """
        DO $$
        BEGIN
            IF EXISTS (SELECT 1 FROM recorrente)
               OR EXISTS (SELECT 1 FROM recorrente_vinculo)
               OR EXISTS (SELECT 1 FROM r2_parametro)
               OR EXISTS (SELECT 1 FROM cartao_vencimento) THEN
                RAISE EXCEPTION USING MESSAGE =
                    '0011: há recorrentes, vínculos, horizonte ou vencimento de cartão que só '
                    'existem nesta versão; o downgrade apagaria dados. Restaure o backup '
                    'anterior à 0011 (ADR 048).';
            END IF;
        END $$
        """
    )
    for assinatura in reversed((*FUNCOES_LEITURA, *FUNCOES_ESCRITA)):
        op.execute(f"DROP FUNCTION {assinatura}")
    op.execute("DROP VIEW vencimento_vigente")
    op.execute("DROP TABLE cartao_vencimento")
    op.execute("DROP VIEW r2_parametro_vigente")
    op.execute("DROP TABLE r2_parametro")
    op.execute("DROP VIEW recorrente_vinculo_efetivo")
    op.execute("DROP VIEW recorrente_vinculo_vigente")
    op.execute("DROP TABLE recorrente_vinculo")
    op.execute("DROP VIEW recorrente_vigente")
    op.execute("DROP TABLE recorrente")
    op.execute("DROP SEQUENCE recorrente_id_seq")
