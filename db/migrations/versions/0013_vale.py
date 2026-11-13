"""vale (VR) com bolsos, sobra com decisão e alerta R5 (SPEC-013, ADR 052)

Revision ID: 0013
Revises: 0012

SQL puro (ADR 025). Só o VR (vale-refeição) tem bolsos; o VA é outra conta de benefício, sem bolsos.

- `vale_parametro`: qual conta de benefício é o VR, a base de trabalho (inicial 200,00) e o destino
  padrão da sobra, com vigência por mês (`vigente_desde` = dia 1). Append-only como
  `reserva_parametro`: para a mesma vigência vale o último gravado (`vale_parametro_vigente`).
- `vale_bolso`: bolso (trabalho|pessoal) de cada versão de despesa do VR, append-only, só por
  `lancamento_gravar` (16º parâmetro `p_bolso DEFAULT NULL`; quem chamava com 15 continua
  funcionando; o guarda do estorno do ADR 044 segue na frente).
- `vale_decisao`: destino da sobra de um mês encerrado, evento append-only com `versao`
  (`vale_decisao_vigente` = a maior versão). Nunca move saldo.
- Escrita só por funções `SECURITY DEFINER` com `search_path` fixo: `vale_parametro_gravar`,
  `vale_decisao_gravar`, `lancamento_gravar`.
- Leituras `INVOKER` com `p_user`: `vale_conta_em`, `vale_mes` e `vale_calculo` (iterativa),
  `vale_situacao`, `beneficios_contas`; e `alertas` ganha o R5 (cinco colunas novas no fim).
- O pipeline não recebe `SELECT` nas tabelas novas nem `EXECUTE` nas funções novas.
- Mensagens de erro literais (sem `||`). Downgrade recusa se houver dado nas tabelas novas.
"""

from __future__ import annotations

import importlib.util
from pathlib import Path
from types import ModuleType

from alembic import op

revision = "0013"
down_revision = "0012"
branch_labels = None
depends_on = None

ASSIN_LANC_ANTIGA = (
    "lancamento_gravar(bigint, bigint, integer, text, date, numeric, bigint, bigint, "
    "numeric, numeric, text, text, text, integer, bigint)"
)
ASSIN_LANC = ASSIN_LANC_ANTIGA[:-1] + ", text)"
ASSIN_ALERTAS = "alertas(bigint, date)"

FUNCOES_LEITURA = (
    "vale_conta_em(bigint, date)",
    "vale_mes(bigint, date, numeric, numeric)",
    "vale_calculo(bigint, date)",
    "vale_situacao(bigint, text, date)",
    "beneficios_contas(bigint, text, date)",
)
FUNCOES_ESCRITA = (
    "vale_parametro_gravar(bigint, bigint, numeric, text, date)",
    "vale_decisao_gravar(bigint, text, text)",
    ASSIN_LANC,
)
TABELAS = ("vale_parametro", "vale_bolso", "vale_decisao")
VIEWS = ("vale_parametro_vigente", "vale_decisao_vigente")

# ---------------------------------------------------------------------------------------------
# Leituras
# ---------------------------------------------------------------------------------------------

# Conta do VR vigente numa data: o parâmetro de maior vigência menor ou igual a ela.
SQL_CONTA_EM = """
CREATE FUNCTION vale_conta_em(p_user bigint, p_data date) RETURNS bigint
LANGUAGE sql STABLE SET search_path = public, pg_temp AS $$
    SELECT p.conta_id FROM vale_parametro_vigente p
    WHERE p.user_id = p_user AND p.vigente_desde <= p_data
    ORDER BY p.vigente_desde DESC
    LIMIT 1
$$
"""

# Números de UM mês com o ajuste dado (p_mes = qualquer dia dele). Não olha decisões: quem
# encadeia os meses é `vale_calculo`.
SQL_MES = """
CREATE FUNCTION vale_mes(p_user bigint, p_mes date, p_aj_t numeric, p_aj_p numeric)
RETURNS TABLE (
    conta_vr bigint, estado text, credito numeric, base_trabalho numeric,
    inicial_trabalho numeric, inicial_pessoal numeric,
    ajuste_trabalho numeric, ajuste_pessoal numeric,
    alocacao_trabalho numeric, alocacao_pessoal numeric,
    consumo_trabalho numeric, consumo_pessoal numeric,
    resta_trabalho numeric, resta_pessoal numeric, sobra numeric
)
LANGUAGE plpgsql STABLE SET search_path = public, pg_temp AS $$
#variable_conflict use_column
DECLARE
    v_mes date := p_mes - (extract(day FROM p_mes)::int - 1);
    v_fim date := (p_mes - (extract(day FROM p_mes)::int - 1) + interval '1 month')::date;
    v_conta bigint;
    v_base numeric;
    v_credito numeric;
    v_ini_t numeric;
    v_ini_p numeric;
    v_aj_t numeric := COALESCE(p_aj_t, 0.00);
    v_aj_p numeric := COALESCE(p_aj_p, 0.00);
    v_con_t numeric;
    v_con_p numeric;
    v_aloc_t numeric;
    v_aloc_p numeric;
    v_resta_t numeric;
    v_resta_p numeric;
BEGIN
    SELECT p.conta_id, p.base_trabalho INTO v_conta, v_base
    FROM vale_parametro_vigente p
    WHERE p.user_id = p_user AND p.vigente_desde <= v_mes
    ORDER BY p.vigente_desde DESC
    LIMIT 1;
    IF NOT FOUND OR NOT EXISTS (
        SELECT 1 FROM conta_versao c
        WHERE c.user_id = p_user AND c.conta_id = v_conta
          AND c.vigente AND NOT c.excluida AND c.tipo = 'beneficio') THEN
        RETURN QUERY SELECT NULL::bigint, 'sem_conta'::text, 0.00, NULL::numeric,
            0.00, 0.00, 0.00, 0.00, 0.00, 0.00, 0.00, 0.00, 0.00, 0.00, 0.00;
        RETURN;
    END IF;

    SELECT COALESCE(sum(t.valor), 0.00) INTO v_credito
    FROM transacao_vigente t
    WHERE t.user_id = p_user AND t.conta_id = v_conta AND t.tipo = 'receita'
      AND t.data_transacao >= v_mes AND t.data_transacao < v_fim;
    v_ini_t := least(v_base, v_credito);
    v_ini_p := greatest(v_credito - v_base, 0.00);

    SELECT COALESCE(sum(-t.valor) FILTER (WHERE b.bolso = 'trabalho'), 0.00),
           COALESCE(sum(-t.valor) FILTER (WHERE b.bolso = 'pessoal'), 0.00)
    INTO v_con_t, v_con_p
    FROM transacao_vigente t
    JOIN vale_bolso b ON b.user_id = t.user_id AND b.transacao_id = t.transacao_id
                     AND b.versao = t.versao
    WHERE t.user_id = p_user AND t.conta_id = v_conta AND t.tipo = 'debito'
      AND t.data_transacao >= v_mes AND t.data_transacao < v_fim;

    v_aloc_t := v_ini_t + v_aj_t;
    v_aloc_p := v_ini_p + v_aj_p;
    v_resta_t := v_aloc_t - v_con_t;
    v_resta_p := v_aloc_p - v_con_p;
    RETURN QUERY SELECT v_conta,
        CASE WHEN v_credito = 0 THEN 'sem_credito' ELSE 'ok' END,
        v_credito, v_base, v_ini_t, v_ini_p, v_aj_t, v_aj_p, v_aloc_t, v_aloc_p,
        v_con_t, v_con_p, v_resta_t, v_resta_p,
        greatest(v_resta_t, 0.00) + greatest(v_resta_p, 0.00);
END
$$
"""


# Números de um mês, ITERATIVA (sem recursão, sem limite de pilha): o ajuste do mês é a sobra do mês
# anterior quando há decisão diferente de `nenhum`; sem decisão, sem ajuste. Volta até o início da
# cadeia de decisões e avança mês a mês até o pedido.
SQL_CALCULO = """
CREATE FUNCTION vale_calculo(p_user bigint, p_mes date)
RETURNS TABLE (
    conta_vr bigint, estado text, credito numeric, base_trabalho numeric,
    inicial_trabalho numeric, inicial_pessoal numeric,
    ajuste_trabalho numeric, ajuste_pessoal numeric,
    alocacao_trabalho numeric, alocacao_pessoal numeric,
    consumo_trabalho numeric, consumo_pessoal numeric,
    resta_trabalho numeric, resta_pessoal numeric, sobra numeric
)
LANGUAGE plpgsql STABLE SET search_path = public, pg_temp AS $$
#variable_conflict use_column
DECLARE
    v_mes date := p_mes - (extract(day FROM p_mes)::int - 1);
    v_cur date;
    v_aj_t numeric := 0.00;
    v_aj_p numeric := 0.00;
    v_dest text;
    v_r RECORD;
BEGIN
    v_cur := v_mes;
    LOOP
        SELECT d.destino INTO v_dest FROM vale_decisao_vigente d
        WHERE d.user_id = p_user AND d.mes = (v_cur - interval '1 month')::date;
        EXIT WHEN NOT FOUND OR v_dest = 'nenhum';
        v_cur := (v_cur - interval '1 month')::date;
    END LOOP;
    LOOP
        SELECT * INTO v_r FROM vale_mes(p_user, v_cur, v_aj_t, v_aj_p);
        EXIT WHEN v_cur = v_mes;
        SELECT d.destino INTO v_dest FROM vale_decisao_vigente d
        WHERE d.user_id = p_user AND d.mes = v_cur;
        v_aj_t := CASE WHEN v_dest = 'trabalho' THEN v_r.sobra ELSE 0.00 END;
        v_aj_p := CASE WHEN v_dest = 'pessoal' THEN v_r.sobra ELSE 0.00 END;
        v_cur := (v_cur + interval '1 month')::date;
    END LOOP;
    RETURN QUERY SELECT v_r.conta_vr, v_r.estado, v_r.credito, v_r.base_trabalho,
        v_r.inicial_trabalho, v_r.inicial_pessoal, v_r.ajuste_trabalho, v_r.ajuste_pessoal,
        v_r.alocacao_trabalho, v_r.alocacao_pessoal, v_r.consumo_trabalho, v_r.consumo_pessoal,
        v_r.resta_trabalho, v_r.resta_pessoal, v_r.sobra;
END
$$
"""

SQL_SITUACAO = """
CREATE FUNCTION vale_situacao(p_user bigint, p_mes text, p_hoje date)
RETURNS TABLE (
    mes text, mes_encerrado boolean, estado text, conta_vr_id bigint,
    credito numeric, base_trabalho numeric,
    inicial_trabalho numeric, inicial_pessoal numeric,
    ajuste_trabalho numeric, ajuste_pessoal numeric,
    alocacao_trabalho numeric, alocacao_pessoal numeric,
    consumo_trabalho numeric, consumo_pessoal numeric,
    resta_trabalho numeric, resta_pessoal numeric, sobra numeric,
    decisao_destino text, decisao_versao integer, destino_padrao text,
    saldo_total numeric, receita_caixa numeric, receita_beneficio numeric, receita_total numeric
)
LANGUAGE plpgsql STABLE SET search_path = public, pg_temp AS $$
#variable_conflict use_column
DECLARE
    v_mes date;
    v_c RECORD;
    v_dest text;
    v_versao integer;
    v_padrao text;
BEGIN
    IF p_hoje IS NULL THEN
        RAISE EXCEPTION USING ERRCODE = 'AB422', MESSAGE = 'a data de hoje é obrigatória';
    END IF;
    v_mes := mes_inicio(p_mes);
    SELECT * INTO v_c FROM vale_calculo(p_user, v_mes);
    SELECT d.destino, d.versao INTO v_dest, v_versao FROM vale_decisao_vigente d
    WHERE d.user_id = p_user AND d.mes = v_mes;
    SELECT p.destino_padrao INTO v_padrao FROM vale_parametro_vigente p
    WHERE p.user_id = p_user AND p.vigente_desde <= v_mes
    ORDER BY p.vigente_desde DESC
    LIMIT 1;
    RETURN QUERY SELECT
        p_mes,
        v_mes < (p_hoje - (extract(day FROM p_hoje)::int - 1)),
        v_c.estado, v_c.conta_vr, v_c.credito, v_c.base_trabalho,
        v_c.inicial_trabalho, v_c.inicial_pessoal, v_c.ajuste_trabalho, v_c.ajuste_pessoal,
        v_c.alocacao_trabalho, v_c.alocacao_pessoal, v_c.consumo_trabalho, v_c.consumo_pessoal,
        v_c.resta_trabalho, v_c.resta_pessoal, v_c.sobra,
        v_dest, v_versao, COALESCE(v_padrao, 'nenhum'),
        CASE WHEN v_c.conta_vr IS NULL THEN NULL
             ELSE saldo_derivado(p_user, v_c.conta_vr, p_hoje) END,
        receita_caixa(p_user, p_mes), receita_beneficio(p_user, p_mes),
        receita_total(p_user, p_mes);
END
$$
"""

# Contas de benefício vigentes (VR e VA): receita e despesa do mês e saldo na data de hoje.
SQL_BENEFICIOS = """
CREATE FUNCTION beneficios_contas(p_user bigint, p_mes text, p_hoje date)
RETURNS TABLE (
    conta_id bigint, vale_refeicao boolean, receita_mes numeric, despesa_mes numeric,
    saldo_total numeric
)
LANGUAGE plpgsql STABLE SET search_path = public, pg_temp AS $$
#variable_conflict use_column
DECLARE
    v_mes date;
    v_fim date;
    v_vr bigint;
BEGIN
    IF p_hoje IS NULL THEN
        RAISE EXCEPTION USING ERRCODE = 'AB422', MESSAGE = 'a data de hoje é obrigatória';
    END IF;
    v_mes := mes_inicio(p_mes);
    v_fim := (v_mes + interval '1 month')::date;
    v_vr := vale_conta_em(p_user, v_mes);
    RETURN QUERY
    SELECT c.conta_id,
           c.conta_id IS NOT DISTINCT FROM v_vr,
           COALESCE((SELECT sum(t.valor) FROM transacao_vigente t
                     WHERE t.user_id = p_user AND t.conta_id = c.conta_id
                       AND t.tipo = 'receita'
                       AND t.data_transacao >= v_mes AND t.data_transacao < v_fim), 0.00),
           COALESCE((SELECT sum(-t.valor) FROM transacao_vigente t
                     WHERE t.user_id = p_user AND t.conta_id = c.conta_id
                       AND t.tipo = 'debito'
                       AND t.data_transacao >= v_mes AND t.data_transacao < v_fim), 0.00),
           saldo_derivado(p_user, c.conta_id, p_hoje)
    FROM conta_versao c
    WHERE c.user_id = p_user AND c.vigente AND NOT c.excluida AND c.tipo = 'beneficio'
    ORDER BY c.conta_id;
END
$$
"""

# ---------------------------------------------------------------------------------------------
# Escrita (SECURITY DEFINER)
# ---------------------------------------------------------------------------------------------

SQL_PARAMETRO_GRAVAR = """
CREATE FUNCTION vale_parametro_gravar(
    p_user bigint, p_conta bigint, p_base numeric, p_destino_padrao text, p_desde date
)
RETURNS bigint
LANGUAGE plpgsql SECURITY DEFINER SET search_path = public, pg_temp AS $$
DECLARE
    v_id bigint;
    v_tipo text;
BEGIN
    IF p_base IS NULL OR p_base < 0 OR p_base >= 1000000000 OR p_base <> round(p_base, 2) THEN
        PERFORM abako_erro('AB422', 'a base de trabalho é zero ou positiva, com até 2 casas');
    END IF;
    IF p_destino_padrao IS NULL OR p_destino_padrao NOT IN ('trabalho', 'pessoal', 'nenhum') THEN
        PERFORM abako_erro('AB422', 'o destino padrão é trabalho, pessoal ou nenhum');
    END IF;
    IF p_desde IS NULL OR p_desde < DATE '2000-01-01' OR extract(day FROM p_desde) <> 1 THEN
        PERFORM abako_erro('AB422',
            'a vigência do vale começa no primeiro dia de um mês a partir de 2000');
    END IF;
    IF p_desde > ((now() AT TIME ZONE 'America/Sao_Paulo')::date + interval '5 years')::date THEN
        PERFORM abako_erro('AB422', 'a vigência não pode passar de 5 anos no futuro');
    END IF;
    PERFORM 1 FROM usuario u WHERE u.user_id = p_user;
    IF NOT FOUND THEN
        PERFORM abako_erro('AB404', 'usuário não encontrado');
    END IF;
    -- Mesma trava e mesma ordem de `lancamento_gravar` (antes de qualquer outra): marcar o VR e
    -- lançar despesa do usuário se serializam; a checagem abaixo vê as despesas já gravadas.
    PERFORM pg_advisory_xact_lock(hashtextextended(p_user::text, 17));
    -- A conta é do usuário, está vigente e é de benefício; não muda de tipo enquanto grava.
    SELECT c.tipo INTO v_tipo FROM conta_versao c
    WHERE c.user_id = p_user AND c.conta_id = p_conta AND c.vigente AND NOT c.excluida
    FOR SHARE;
    IF NOT FOUND THEN
        PERFORM abako_erro('AB404', 'conta não encontrada');
    END IF;
    IF v_tipo <> 'beneficio' THEN
        PERFORM abako_erro('AB422', 'a conta do vale precisa ser de benefício');
    END IF;
    -- Idempotente: repetir o que já vale para essa vigência devolve o registro existente.
    SELECT v.id INTO v_id FROM vale_parametro_vigente v
    WHERE v.user_id = p_user AND v.vigente_desde = p_desde AND v.conta_id = p_conta
      AND v.base_trabalho = p_base AND v.destino_padrao = p_destino_padrao;
    IF FOUND THEN
        RETURN v_id;
    END IF;
    INSERT INTO vale_parametro (user_id, conta_id, base_trabalho, destino_padrao, vigente_desde)
    VALUES (p_user, p_conta, p_base, p_destino_padrao, p_desde)
    RETURNING id INTO v_id;
    -- Só os meses em que ESTA conta passa a ser o VR (com a vigência já gravada, vale_conta_em
    -- respeita as vigências posteriores): despesa vigente sem bolso nesses meses é recusada e o
    -- INSERT acima é desfeito. Antes de marcar, o bolso pode ser informado na própria despesa.
    IF EXISTS (
        SELECT 1 FROM transacao_vigente t
        WHERE t.user_id = p_user AND t.conta_id = p_conta AND t.tipo = 'debito'
          AND t.data_transacao >= p_desde
          AND vale_conta_em(p_user, t.data_transacao) = p_conta
          AND NOT EXISTS (
              SELECT 1 FROM vale_bolso b
              WHERE b.user_id = t.user_id AND b.transacao_id = t.transacao_id
                AND b.versao = t.versao)) THEN
        PERFORM abako_erro('AB422',
            'edite as despesas antigas da conta informando o bolso antes de marcá-la como VR');
    END IF;
    RETURN v_id;
END
$$
"""

# Devolve a versão vigente da decisão do mês (a existente, se o destino é o mesmo).
SQL_DECISAO_GRAVAR = """
CREATE FUNCTION vale_decisao_gravar(p_user bigint, p_mes text, p_destino text)
RETURNS integer
LANGUAGE plpgsql SECURITY DEFINER SET search_path = public, pg_temp AS $$
DECLARE
    v_mes date := mes_inicio(p_mes);
    v_hoje date := (now() AT TIME ZONE 'America/Sao_Paulo')::date;
    v_atual RECORD;
    v_versao integer;
BEGIN
    IF p_destino IS NULL OR p_destino NOT IN ('trabalho', 'pessoal', 'nenhum') THEN
        PERFORM abako_erro('AB422', 'o destino da sobra é trabalho, pessoal ou nenhum');
    END IF;
    PERFORM 1 FROM usuario u WHERE u.user_id = p_user;
    IF NOT FOUND THEN
        PERFORM abako_erro('AB404', 'usuário não encontrado');
    END IF;
    IF v_mes >= (v_hoje - (extract(day FROM v_hoje)::int - 1)) THEN
        PERFORM abako_erro('AB422', 'só se decide a sobra de um mês encerrado');
    END IF;
    IF vale_conta_em(p_user, v_mes) IS NULL THEN
        PERFORM abako_erro('AB422', 'o mês não tem conta de vale configurada');
    END IF;
    -- Duas decisões simultâneas do mesmo mês esperam uma pela outra (versões sem buraco).
    PERFORM pg_advisory_xact_lock(
        hashtextextended(p_user::text, 13)
        # (extract(year FROM v_mes)::bigint * 12 + extract(month FROM v_mes)::bigint));
    SELECT d.destino, d.versao INTO v_atual FROM vale_decisao_vigente d
    WHERE d.user_id = p_user AND d.mes = v_mes;
    IF FOUND AND v_atual.destino = p_destino THEN
        RETURN v_atual.versao;
    END IF;
    v_versao := COALESCE(v_atual.versao, 0) + 1;
    INSERT INTO vale_decisao (user_id, mes, destino, versao)
    VALUES (p_user, v_mes, p_destino, v_versao);
    RETURN v_versao;
END
$$
"""

# Função pública de escrita: a da 0008 mais o bolso. A despesa na conta do VR vigente na data
# exige bolso; fora dela o bolso é proibido. O bolso é gravado junto da versão criada.
SQL_LANCAMENTO_GRAVAR = """
CREATE FUNCTION lancamento_gravar(
    p_user bigint, p_transacao bigint, p_versao integer,
    p_tipo text, p_data date, p_valor numeric,
    p_conta bigint, p_conta_destino bigint,
    p_bruto numeric, p_imposto numeric, p_descricao text,
    p_chave text, p_hash text, p_parcelas integer DEFAULT NULL, p_pessoa bigint DEFAULT NULL,
    p_bolso text DEFAULT NULL
)
RETURNS TABLE (transacao_id bigint, versao integer, criado boolean)
LANGUAGE plpgsql SECURITY DEFINER SET search_path = public, pg_temp AS $$
DECLARE
    v_alvo bigint;
    v_vr bigint;
    v_tipo_conta text;
    v_exige boolean := false;
    v_permite boolean := false;
    r RECORD;
BEGIN
    -- Trava por usuário ANTES de qualquer outra (cartao_trava vem depois): serializa o lançamento
    -- de despesa com `vale_parametro_gravar`, que toma a mesma trava primeiro.
    IF p_tipo = 'debito' OR p_bolso IS NOT NULL THEN
        PERFORM pg_advisory_xact_lock(hashtextextended(p_user::text, 17));
    END IF;
    IF p_bolso IS NOT NULL AND p_bolso NOT IN ('trabalho', 'pessoal') THEN
        PERFORM abako_erro('AB422', 'o bolso é trabalho ou pessoal');
    END IF;
    -- Despesa na conta do VR da data: bolso obrigatório. Em conta de benefício quando NÃO há VR
    -- marcado na data: bolso opcional (classificar antes de marcar). Nos demais casos (inclusive
    -- o VA quando outra conta é o VR): proibido.
    IF p_tipo = 'debito' AND p_data IS NOT NULL AND p_conta IS NOT NULL THEN
        v_vr := vale_conta_em(p_user, p_data);
        IF v_vr IS NOT NULL AND v_vr = p_conta THEN
            v_exige := true;
        ELSIF v_vr IS NULL THEN
            SELECT c.tipo INTO v_tipo_conta FROM conta_versao c
            WHERE c.user_id = p_user AND c.conta_id = p_conta AND c.vigente AND NOT c.excluida;
            v_permite := FOUND AND v_tipo_conta = 'beneficio';
        END IF;
    END IF;
    IF v_exige AND p_bolso IS NULL THEN
        PERFORM abako_erro('AB422', 'a despesa do vale precisa de bolso: trabalho ou pessoal');
    ELSIF p_bolso IS NOT NULL AND NOT (v_exige OR v_permite) THEN
        PERFORM abako_erro('AB422',
            'bolso só na despesa da conta do vale ou de conta de benefício sem vale marcado');
    END IF;
    -- Cartão que receberá a compra a crédito ou o pagamento: trava (e, na conversão, confere)
    -- tanto na criação quanto na edição (guarda do estorno, ADR 044).
    v_alvo := CASE WHEN p_tipo = 'credito' THEN p_conta
                   WHEN p_tipo = 'transferencia' THEN p_conta_destino END;
    IF p_transacao IS NOT NULL OR v_alvo IS NOT NULL THEN
        PERFORM estorno_guarda(p_user, p_transacao, 'editar', v_alvo);
    END IF;
    FOR r IN
        SELECT b.transacao_id AS tid, b.versao AS ver, b.criado AS cri
        FROM lancamento_gravar_base(
            p_user, p_transacao, p_versao, p_tipo, p_data, p_valor, p_conta, p_conta_destino,
            p_bruto, p_imposto, p_descricao, p_chave, p_hash, p_parcelas, p_pessoa) b
    LOOP
        IF p_bolso IS NOT NULL AND r.cri THEN
            INSERT INTO vale_bolso (user_id, transacao_id, versao, bolso)
            VALUES (p_user, r.tid, r.ver, p_bolso);
        END IF;
        transacao_id := r.tid;
        versao := r.ver;
        criado := r.cri;
        RETURN NEXT;
    END LOOP;
END
$$
"""

# ---------------------------------------------------------------------------------------------
# alertas: R1, R2, R4 (como na 0012) e R5
# ---------------------------------------------------------------------------------------------

SQL_ALERTAS = """
CREATE FUNCTION alertas(p_user bigint, p_hoje date)
RETURNS TABLE (
    codigo text, tipo text, severidade text, detalhe text, mensagem text,
    nivel text, saldo_liquido numeric, meta numeric, falta numeric, cobertura_meses numeric,
    horizonte_dias integer, data_fim date, sobra numeric, disponivel numeric,
    compromissos numeric, sobra_nao_confiavel boolean, vencidas integer,
    pendencias_vencimento integer,
    conta_id bigint, data_snapshot date, valor_snapshot numeric, saldo_derivado numeric,
    divergencia numeric, quantidade integer,
    bolso text, alocacao numeric, consumo numeric, resta numeric, mes text
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
    v AS (SELECT * FROM vale_calculo(p_user, p_hoje)),
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
               NULL::numeric AS divergencia, NULL::integer AS quantidade,
               NULL::text AS bolso, NULL::numeric AS alocacao, NULL::numeric AS consumo,
               NULL::numeric AS resta, NULL::text AS mes
        FROM r
        WHERE NOT r.config_pendente AND r.nivel IN ('critica', 'atencao')
        UNION ALL
        SELECT 'CONFIG', 'configuracao', 'baixa', 'reserva_gasto_essencial',
               'informe o gasto essencial para calcular a meta da reserva',
               NULL, r.saldo_liquido, NULL, NULL, NULL,
               NULL, NULL, NULL, NULL, NULL, NULL, NULL, NULL,
               NULL, NULL, NULL, NULL, NULL, NULL,
               NULL, NULL, NULL, NULL, NULL
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
               NULL, NULL, NULL, NULL, NULL, NULL,
               NULL, NULL, NULL, NULL, NULL
        FROM s
        WHERE s.alerta
        UNION ALL
        SELECT 'R2', 'aviso', 'media', 'sobra_nao_confiavel',
               'a sobra não é confiável: há cartão com dívida sem vencimento ou fechamento',
               NULL, NULL, NULL, NULL, NULL,
               s.horizonte_dias, s.data_fim, s.sobra, s.disponivel, s.compromissos,
               true, s.vencidas, s.pendencias_vencimento,
               NULL, NULL, NULL, NULL, NULL, NULL,
               NULL, NULL, NULL, NULL, NULL
        FROM s
        WHERE NOT s.alerta AND s.pendencias_vencimento > 0
        UNION ALL
        SELECT 'R2', 'aviso', 'baixa', 'vencidas',
               'há ocorrências recorrentes vencidas sem vínculo a uma transação',
               NULL, NULL, NULL, NULL, NULL,
               s.horizonte_dias, s.data_fim, s.sobra, s.disponivel, s.compromissos,
               s.pendencias_vencimento > 0, s.vencidas, s.pendencias_vencimento,
               NULL, NULL, NULL, NULL, NULL, NULL,
               NULL, NULL, NULL, NULL, NULL
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
               d.quantidade,
               NULL, NULL, NULL, NULL, NULL
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
        UNION ALL
        -- R5: só o mês corrente, só com crédito no mês, um alerta por bolso com resta < 0
        -- (estrito); um bolso não compensa o outro (INV-25).
        SELECT 'R5', 'alerta', 'alta', 'vale_trabalho_estourado',
               'o bolso de trabalho do vale está estourado no mês',
               NULL, NULL, NULL, NULL, NULL,
               NULL, NULL, NULL, NULL, NULL, NULL, NULL, NULL,
               v.conta_vr, NULL, NULL, NULL, NULL, NULL,
               'trabalho', v.alocacao_trabalho, v.consumo_trabalho, v.resta_trabalho,
               to_char(p_hoje, 'YYYY-MM')
        FROM v
        WHERE v.estado = 'ok' AND v.resta_trabalho < 0
        UNION ALL
        SELECT 'R5', 'alerta', 'alta', 'vale_pessoal_estourado',
               'o bolso pessoal do vale está estourado no mês',
               NULL, NULL, NULL, NULL, NULL,
               NULL, NULL, NULL, NULL, NULL, NULL, NULL, NULL,
               v.conta_vr, NULL, NULL, NULL, NULL, NULL,
               'pessoal', v.alocacao_pessoal, v.consumo_pessoal, v.resta_pessoal,
               to_char(p_hoje, 'YYYY-MM')
        FROM v
        WHERE v.estado = 'ok' AND v.resta_pessoal < 0
    )
    SELECT a.codigo, a.tipo, a.severidade, a.detalhe, a.mensagem,
           a.nivel, a.saldo_liquido, a.meta, a.falta, a.cobertura_meses,
           a.horizonte_dias, a.data_fim, a.sobra, a.disponivel, a.compromissos,
           a.sobra_nao_confiavel, a.vencidas, a.pendencias_vencimento,
           a.conta_id, a.data_snapshot, a.valor_snapshot, a.saldo_derivado, a.divergencia,
           a.quantidade, a.bolso, a.alocacao, a.consumo, a.resta, a.mes
    FROM a
    ORDER BY CASE a.severidade WHEN 'alta' THEN 1 WHEN 'media' THEN 2 ELSE 3 END,
             a.codigo, a.detalhe, a.conta_id;
END
$$
"""


def _anterior(arquivo: str) -> ModuleType:
    """Carrega uma migração anterior só para reaproveitar suas definições no downgrade."""
    caminho = Path(__file__).resolve().parent / arquivo
    spec = importlib.util.spec_from_file_location(f"_abako_{caminho.stem}", caminho)
    assert spec is not None and spec.loader is not None
    modulo = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(modulo)
    return modulo


def upgrade() -> None:
    op.execute(
        """
        CREATE TABLE vale_parametro (
            id             bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
            user_id        bigint  NOT NULL REFERENCES usuario (user_id),
            conta_id       bigint  NOT NULL,
            base_trabalho  numeric(14, 2) NOT NULL CHECK (base_trabalho >= 0),
            destino_padrao text    NOT NULL
                           CHECK (destino_padrao IN ('trabalho', 'pessoal', 'nenhum')),
            vigente_desde  date    NOT NULL
                           CHECK (vigente_desde >= DATE '2000-01-01'
                                  AND extract(day FROM vigente_desde) = 1),
            registrado_em  timestamptz NOT NULL DEFAULT now()
        )
        """
    )
    op.execute(
        "CREATE INDEX vale_parametro_user_idx ON vale_parametro "
        "(user_id, vigente_desde, registrado_em)"
    )
    op.execute(
        """
        CREATE VIEW vale_parametro_vigente WITH (security_invoker = true) AS
        SELECT DISTINCT ON (user_id, vigente_desde)
               id, user_id, conta_id, base_trabalho, destino_padrao, vigente_desde, registrado_em
        FROM vale_parametro
        ORDER BY user_id, vigente_desde, registrado_em DESC, id DESC
        """
    )
    op.execute(
        """
        CREATE TABLE vale_bolso (
            user_id      bigint  NOT NULL REFERENCES usuario (user_id),
            transacao_id bigint  NOT NULL,
            versao       integer NOT NULL CHECK (versao >= 1),
            bolso        text    NOT NULL CHECK (bolso IN ('trabalho', 'pessoal')),
            registrado_em timestamptz NOT NULL DEFAULT now(),
            PRIMARY KEY (user_id, transacao_id, versao)
        )
        """
    )
    op.execute(
        """
        CREATE TABLE vale_decisao (
            id            bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
            user_id       bigint  NOT NULL REFERENCES usuario (user_id),
            mes           date    NOT NULL
                          CHECK (mes >= DATE '2000-01-01' AND extract(day FROM mes) = 1),
            destino       text    NOT NULL CHECK (destino IN ('trabalho', 'pessoal', 'nenhum')),
            versao        integer NOT NULL CHECK (versao >= 1),
            registrado_em timestamptz NOT NULL DEFAULT now(),
            UNIQUE (user_id, mes, versao)
        )
        """
    )
    op.execute(
        """
        CREATE VIEW vale_decisao_vigente WITH (security_invoker = true) AS
        SELECT DISTINCT ON (user_id, mes)
               id, user_id, mes, destino, versao, registrado_em
        FROM vale_decisao
        ORDER BY user_id, mes, versao DESC
        """
    )

    op.execute(SQL_CONTA_EM)
    op.execute(SQL_MES)
    op.execute(SQL_CALCULO)
    op.execute(SQL_SITUACAO)
    op.execute(SQL_BENEFICIOS)
    op.execute(SQL_PARAMETRO_GRAVAR)
    op.execute(SQL_DECISAO_GRAVAR)
    # A assinatura de 15 argumentos sai; a de 16 (último com DEFAULT) atende quem chamava com 15.
    op.execute(f"DROP FUNCTION {ASSIN_LANC_ANTIGA}")
    op.execute(SQL_LANCAMENTO_GRAVAR)
    op.execute(f"DROP FUNCTION {ASSIN_ALERTAS}")
    op.execute(SQL_ALERTAS)

    # Papéis: o app lê as tabelas e escreve só pelas funções; o pipeline não recebe nada.
    for objeto in (*TABELAS, *VIEWS):
        op.execute(f"GRANT SELECT ON {objeto} TO abako_app")
    for assinatura in (*FUNCOES_LEITURA, *FUNCOES_ESCRITA, ASSIN_ALERTAS):
        op.execute(f"REVOKE ALL ON FUNCTION {assinatura} FROM PUBLIC")
        op.execute(f"GRANT EXECUTE ON FUNCTION {assinatura} TO abako_app")


def downgrade() -> None:
    # Recusa se houver dado: o downgrade apagaria vale, bolsos e decisões do usuário.
    op.execute(
        """
        DO $$
        BEGIN
            IF EXISTS (SELECT 1 FROM vale_parametro)
               OR EXISTS (SELECT 1 FROM vale_bolso)
               OR EXISTS (SELECT 1 FROM vale_decisao) THEN
                RAISE EXCEPTION USING MESSAGE =
                    '0013: há parâmetro, bolso ou decisão do vale que só existem nesta versão; '
                    'o downgrade apagaria dados. Restaure o backup anterior à 0013 (ADR 052).';
            END IF;
        END $$
        """
    )
    m8 = _anterior("0008_terceiros_repasse.py")
    m12 = _anterior("0012_alertas.py")

    op.execute(f"DROP FUNCTION {ASSIN_ALERTAS}")
    op.execute(m12.SQL_ALERTAS)
    op.execute(f"REVOKE ALL ON FUNCTION {ASSIN_ALERTAS} FROM PUBLIC")
    op.execute(f"GRANT EXECUTE ON FUNCTION {ASSIN_ALERTAS} TO abako_app")

    op.execute(f"DROP FUNCTION {ASSIN_LANC}")
    op.execute(m8.SQL_LANCAMENTO_GRAVAR)
    op.execute(f"REVOKE ALL ON FUNCTION {ASSIN_LANC_ANTIGA} FROM PUBLIC")
    op.execute(f"GRANT EXECUTE ON FUNCTION {ASSIN_LANC_ANTIGA} TO abako_app")

    for assinatura in (
        "vale_decisao_gravar(bigint, text, text)",
        "vale_parametro_gravar(bigint, bigint, numeric, text, date)",
        *reversed(FUNCOES_LEITURA),
    ):
        op.execute(f"DROP FUNCTION {assinatura}")
    op.execute("DROP VIEW vale_decisao_vigente")
    op.execute("DROP VIEW vale_parametro_vigente")
    op.execute("DROP TABLE vale_decisao")
    op.execute("DROP TABLE vale_bolso")
    op.execute("DROP TABLE vale_parametro")
