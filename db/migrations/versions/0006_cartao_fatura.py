"""cartão (conta de dívida), fatura, parcelas e linha de crédito (SPEC-005, ADR 043)

Revision ID: 0006
Revises: 0005

SQL puro (ADR 025). A regra vive no banco (ADR 015):

- Tipo de conta `divida` (o cartão); todo cartão pertence a uma `linha_credito` (limite versionado).
- `cartao_fechamento`: dia de fechamento (1..31) com `vigente_desde`, append-only; vale o dia
  vigente na data da compra. Dia inexistente no mês usa o último dia válido (INV-31).
- `transacao_versao.parcela/competencia`. Compra a crédito = 1 linha por parcela (mesmo
  `transacao_id`), valor NEGATIVO, data da compra em todas, competência (mês do fechamento) gravada
  e nunca recalculada sozinha. Compra no dia do fechamento ou depois cai na fatura seguinte.
- As n-1 primeiras parcelas valem o total dividido por n truncado em centavos; a última absorve o
  resto (INV-02). Sem juros.
- Pagar a fatura é transferência da corrente para a conta de dívida (parcial permitido).
- Leitura: `fatura_itens`, `fatura_total`, `limite_linha` (limite usado = -soma dos saldos das
  dívidas da linha, INV-06; disponível pode ser negativo, nada bloqueia a compra).
- Escrita só por funções SECURITY DEFINER; `abako_app` não tem INSERT/UPDATE/DELETE nas tabelas
  novas. `conta_gravar` e `lancamento_gravar` ganham um parâmetro final com DEFAULT NULL (quem
  chamava com os argumentos antigos continua funcionando); as assinaturas antigas saem.
"""

from alembic import op

revision = "0006"
down_revision = "0005"
branch_labels = None
depends_on = None

TIPOS_CONTA = "'corrente', 'reserva', 'investimento', 'beneficio', 'divida'"
TIPOS_CONTA_ANTIGOS = "'corrente', 'reserva', 'investimento', 'beneficio'"

ASSIN_CONTA_NOVA = "conta_gravar(bigint, bigint, integer, text, text, bigint, bigint)"
ASSIN_CONTA_ANTIGA = "conta_gravar(bigint, bigint, integer, text, text, bigint)"
ASSIN_LANC_NOVA = (
    "lancamento_gravar(bigint, bigint, integer, text, date, numeric, bigint, bigint, "
    "numeric, numeric, text, text, text, integer)"
)
ASSIN_LANC_ANTIGA = (
    "lancamento_gravar(bigint, bigint, integer, text, date, numeric, bigint, bigint, "
    "numeric, numeric, text, text, text)"
)

FUNCOES_NOVAS = (
    "linha_credito_gravar(bigint, bigint, integer, text, numeric)",
    "fechamento_gravar(bigint, bigint, integer, date)",
    "fechamento_efetivo(integer, date)",
    "competencia_compra(bigint, bigint, date)",
    "fatura_itens(bigint, bigint, text)",
    "fatura_total(bigint, bigint, text)",
    "limite_linha(bigint, bigint, date)",
)

# ---------------------------------------------------------------------------------------------
# Funções novas (upgrade)
# ---------------------------------------------------------------------------------------------

SQL_CONTA_GRAVAR = """
CREATE FUNCTION conta_gravar(
    p_user bigint, p_conta bigint, p_versao integer,
    p_nome text, p_tipo text, p_conta_mae bigint, p_linha bigint DEFAULT NULL
)
RETURNS TABLE (conta_id bigint, versao integer)
LANGUAGE plpgsql SECURITY DEFINER SET search_path = public, pg_temp AS $$
DECLARE
    v_nome text := btrim(coalesce(p_nome, ''));
    v_atual conta_versao%ROWTYPE;
    v_id bigint;
    v_versao integer;
BEGIN
    IF v_nome = '' OR length(v_nome) > 80 THEN
        PERFORM abako_erro('AB422', 'o nome precisa ter de 1 a 80 caracteres');
    END IF;
    IF p_tipo IS NULL
       OR p_tipo NOT IN ('corrente', 'reserva', 'investimento', 'beneficio', 'divida') THEN
        PERFORM abako_erro('AB422', 'tipo de conta inválido');
    END IF;
    IF p_conta_mae IS NOT NULL THEN
        IF p_tipo NOT IN ('reserva', 'investimento') THEN
            PERFORM abako_erro('AB422',
                'só reserva ou investimento pertence a outra conta');
        END IF;
        -- FOR SHARE: o banco não deixa de ser corrente enquanto esta conta é gravada.
        PERFORM 1 FROM conta_versao c
        WHERE c.user_id = p_user AND c.conta_id = p_conta_mae
          AND c.vigente AND NOT c.excluida AND c.tipo = 'corrente'
        FOR SHARE;
        IF p_conta_mae IS NOT DISTINCT FROM p_conta OR NOT FOUND THEN
            PERFORM abako_erro('AB422', 'a conta do banco precisa ser uma conta corrente');
        END IF;
    END IF;
    IF p_tipo = 'divida' THEN
        IF p_linha IS NULL THEN
            PERFORM abako_erro('AB422', 'o cartão precisa pertencer a uma linha de crédito');
        END IF;
        PERFORM 1 FROM linha_credito l
        WHERE l.user_id = p_user AND l.linha_id = p_linha AND l.vigente AND NOT l.excluida
        FOR SHARE;
        IF NOT FOUND THEN
            PERFORM abako_erro('AB422', 'linha de crédito não encontrada');
        END IF;
    ELSIF p_linha IS NOT NULL THEN
        PERFORM abako_erro('AB422', 'só o cartão pertence a uma linha de crédito');
    END IF;

    IF p_conta IS NULL THEN
        v_id := nextval('conta_id_seq');
        v_versao := 1;
    ELSE
        IF p_versao IS NULL THEN
            PERFORM abako_erro('AB422', 'editar conta exige a versão lida');
        END IF;
        SELECT * INTO v_atual FROM conta_versao c
        WHERE c.user_id = p_user AND c.conta_id = p_conta AND c.vigente
          AND NOT c.excluida
        FOR UPDATE;
        IF NOT FOUND THEN
            -- Outra edição pode ter fechado a linha enquanto esta esperava a trava: a
            -- conta existe, só mudou (INV-29). Uma nova leitura já vê a versão nova.
            IF EXISTS (SELECT 1 FROM conta_versao c
                       WHERE c.user_id = p_user AND c.conta_id = p_conta
                         AND c.vigente AND NOT c.excluida) THEN
                PERFORM abako_erro('AB409', 'a conta mudou desde a última leitura');
            END IF;
            PERFORM abako_erro('AB404', 'conta não encontrada');
        END IF;
        IF v_atual.versao IS DISTINCT FROM p_versao THEN
            PERFORM abako_erro('AB409', 'a conta mudou desde a última leitura');
        END IF;
        IF v_atual.tipo <> p_tipo THEN
            IF (v_atual.tipo = 'beneficio' OR p_tipo = 'beneficio') AND EXISTS (
                SELECT 1 FROM transacao_versao t
                WHERE t.user_id = p_user AND t.conta_id = p_conta
                  AND t.vigente AND NOT t.excluida
            ) THEN
                PERFORM abako_erro('AB422',
                    'conta com lançamentos não entra nem sai do tipo benefício');
            END IF;
            IF (v_atual.tipo = 'divida' OR p_tipo = 'divida') AND EXISTS (
                SELECT 1 FROM transacao_versao t
                WHERE t.user_id = p_user AND t.conta_id = p_conta
                  AND t.vigente AND NOT t.excluida
            ) THEN
                PERFORM abako_erro('AB422',
                    'conta com lançamentos não entra nem sai do tipo cartão');
            END IF;
            IF v_atual.tipo = 'investimento' AND EXISTS (
                SELECT 1 FROM transacao_versao t
                WHERE t.user_id = p_user AND t.conta_id = p_conta AND t.perna = 2
                  AND t.tipo = 'investimento' AND t.vigente AND NOT t.excluida
            ) THEN
                PERFORM abako_erro('AB422',
                    'conta que recebeu investimento continua do tipo investimento');
            END IF;
            IF v_atual.tipo = 'corrente' AND EXISTS (
                SELECT 1 FROM conta_versao c
                WHERE c.user_id = p_user AND c.conta_mae_id = p_conta
                  AND c.vigente AND NOT c.excluida
            ) THEN
                PERFORM abako_erro('AB422',
                    'esta conta tem reserva ou investimento ligado a ela');
            END IF;
        END IF;
        UPDATE conta_versao c SET vigente = false WHERE c.id = v_atual.id;
        v_id := p_conta;
        v_versao := v_atual.versao + 1;
    END IF;

    BEGIN
        INSERT INTO conta_versao
            (user_id, conta_id, versao, nome, tipo, conta_beneficio, conta_mae_id,
             linha_credito_id)
        VALUES (p_user, v_id, v_versao, v_nome, p_tipo, p_tipo = 'beneficio',
                p_conta_mae, p_linha);
    EXCEPTION WHEN unique_violation THEN
        PERFORM abako_erro('AB410', 'já existe uma conta com esse nome');
    END;
    RETURN QUERY SELECT v_id, v_versao;
END
$$
"""

SQL_LINHA_GRAVAR = """
CREATE FUNCTION linha_credito_gravar(
    p_user bigint, p_linha bigint, p_versao integer, p_nome text, p_limite numeric
)
RETURNS TABLE (linha_id bigint, versao integer)
LANGUAGE plpgsql SECURITY DEFINER SET search_path = public, pg_temp AS $$
DECLARE
    v_nome text := btrim(coalesce(p_nome, ''));
    v_atual linha_credito%ROWTYPE;
    v_id bigint;
    v_versao integer;
BEGIN
    IF v_nome = '' OR length(v_nome) > 80 THEN
        PERFORM abako_erro('AB422', 'o nome precisa ter de 1 a 80 caracteres');
    END IF;
    IF p_limite IS NULL OR p_limite < 0 OR p_limite > 999999999999.99
       OR p_limite <> round(p_limite, 2) THEN
        PERFORM abako_erro('AB422', 'o limite precisa ser zero ou positivo, com até 2 casas');
    END IF;
    IF p_linha IS NULL THEN
        v_id := nextval('linha_credito_id_seq');
        v_versao := 1;
    ELSE
        IF p_versao IS NULL THEN
            PERFORM abako_erro('AB422', 'editar a linha exige a versão lida');
        END IF;
        SELECT * INTO v_atual FROM linha_credito l
        WHERE l.user_id = p_user AND l.linha_id = p_linha AND l.vigente AND NOT l.excluida
        FOR UPDATE;
        IF NOT FOUND THEN
            IF EXISTS (SELECT 1 FROM linha_credito l
                       WHERE l.user_id = p_user AND l.linha_id = p_linha
                         AND l.vigente AND NOT l.excluida) THEN
                PERFORM abako_erro('AB409', 'a linha mudou desde a última leitura');
            END IF;
            PERFORM abako_erro('AB404', 'linha de crédito não encontrada');
        END IF;
        IF v_atual.versao IS DISTINCT FROM p_versao THEN
            PERFORM abako_erro('AB409', 'a linha mudou desde a última leitura');
        END IF;
        UPDATE linha_credito l SET vigente = false WHERE l.id = v_atual.id;
        v_id := p_linha;
        v_versao := v_atual.versao + 1;
    END IF;
    BEGIN
        INSERT INTO linha_credito (user_id, linha_id, versao, nome, limite)
        VALUES (p_user, v_id, v_versao, v_nome, p_limite);
    EXCEPTION WHEN unique_violation THEN
        PERFORM abako_erro('AB410', 'já existe uma linha de crédito com esse nome');
    END;
    RETURN QUERY SELECT v_id, v_versao;
END
$$
"""

SQL_FECHAMENTO_GRAVAR = """
CREATE FUNCTION fechamento_gravar(
    p_user bigint, p_conta bigint, p_dia integer, p_desde date
)
RETURNS bigint
LANGUAGE plpgsql SECURITY DEFINER SET search_path = public, pg_temp AS $$
DECLARE
    v_id bigint;
BEGIN
    IF p_dia IS NULL OR p_dia < 1 OR p_dia > 31 THEN
        PERFORM abako_erro('AB422', 'o dia de fechamento vai de 1 a 31');
    END IF;
    IF p_desde IS NULL OR p_desde < DATE '2000-01-01' THEN
        PERFORM abako_erro('AB422', 'a vigência precisa ser uma data a partir de 2000');
    END IF;
    PERFORM 1 FROM conta_versao c
    WHERE c.user_id = p_user AND c.conta_id = p_conta AND c.vigente AND NOT c.excluida
      AND c.tipo = 'divida'
    FOR SHARE;
    IF NOT FOUND THEN
        PERFORM abako_erro('AB404', 'cartão não encontrado');
    END IF;
    -- Idempotente: repetir o que já vale para essa vigência devolve o registro existente, para
    -- o histórico append-only não crescer com repetições.
    SELECT v.id INTO v_id FROM fechamento_vigente v
    WHERE v.user_id = p_user AND v.conta_id = p_conta AND v.vigente_desde = p_desde
      AND v.dia = p_dia;
    IF FOUND THEN
        RETURN v_id;
    END IF;
    INSERT INTO cartao_fechamento (user_id, conta_id, dia, vigente_desde)
    VALUES (p_user, p_conta, p_dia, p_desde)
    RETURNING id INTO v_id;
    RETURN v_id;
END
$$
"""

SQL_FECHAMENTO_EFETIVO = """
CREATE FUNCTION fechamento_efetivo(p_dia integer, p_mes date)
RETURNS date
LANGUAGE sql IMMUTABLE AS $$
    SELECT s.primeiro + (least(
               p_dia,
               extract(day FROM (s.primeiro + interval '1 month' - interval '1 day'))::int
           ) - 1)
    FROM (SELECT make_date(extract(year FROM p_mes)::int,
                           extract(month FROM p_mes)::int, 1) AS primeiro) s
$$
"""

# Compra antes do fechamento do mês da compra: fatura desse mês; no dia ou depois: a seguinte.
SQL_COMPETENCIA_COMPRA = """
CREATE FUNCTION competencia_compra(p_user bigint, p_conta bigint, p_data date)
RETURNS text
LANGUAGE sql STABLE AS $$
    WITH f AS (
        SELECT v.dia FROM fechamento_vigente v
        WHERE v.user_id = p_user AND v.conta_id = p_conta AND v.vigente_desde <= p_data
        ORDER BY v.vigente_desde DESC
        LIMIT 1
    )
    SELECT to_char(
        make_date(extract(year FROM p_data)::int, extract(month FROM p_data)::int, 1)
        + CASE WHEN p_data < fechamento_efetivo(f.dia, p_data)
               THEN interval '0 month' ELSE interval '1 month' END,
        'YYYY-MM')
    FROM f
$$
"""

SQL_LANCAMENTO_GRAVAR = """
CREATE FUNCTION lancamento_gravar(
    p_user bigint, p_transacao bigint, p_versao integer,
    p_tipo text, p_data date, p_valor numeric,
    p_conta bigint, p_conta_destino bigint,
    p_bruto numeric, p_imposto numeric, p_descricao text,
    p_chave text, p_hash text, p_parcelas integer DEFAULT NULL
)
RETURNS TABLE (transacao_id bigint, versao integer, criado boolean)
LANGUAGE plpgsql SECURITY DEFINER SET search_path = public, pg_temp AS $$
DECLARE
    v_hoje date := (now() AT TIME ZONE 'America/Sao_Paulo')::date;
    v_tipo_conta text;
    v_tipo_destino text;
    v_valor numeric;
    v_id bigint;
    v_versao integer;
    v_existente RECORD;
    v_fechadas integer;
    v_descricao text := nullif(btrim(p_descricao), '');
    v_ant RECORD;
    v_comp text;
    v_base numeric;
BEGIN
    -- Repetição da criação com a mesma chave (INV-28). A trava por (usuário, chave) faz
    -- a segunda requisição simultânea esperar a primeira terminar e então achar o
    -- lançamento dela, em vez de bater no índice único.
    IF p_transacao IS NULL AND p_chave IS NOT NULL THEN
        PERFORM pg_advisory_xact_lock(hashtextextended(p_user::text || ':' || p_chave, 0));
        SELECT t.transacao_id, t.hash_corpo INTO v_existente FROM transacao_versao t
        WHERE t.user_id = p_user AND t.chave_idempotencia = p_chave;
        IF FOUND THEN
            IF v_existente.hash_corpo IS DISTINCT FROM p_hash THEN
                PERFORM abako_erro('AB422', 'chave já usada com outros dados');
            END IF;
            RETURN QUERY
                SELECT t.transacao_id, t.versao, false FROM transacao_versao t
                WHERE t.user_id = p_user AND t.transacao_id = v_existente.transacao_id
                  AND t.vigente AND t.perna = 1 AND t.parcela = 1;
            RETURN;
        END IF;
    END IF;

    IF p_tipo = 'repasse' THEN
        PERFORM abako_erro('AB422', 'esse tipo de lançamento ainda não está disponível');
    END IF;
    IF p_tipo IS NULL OR p_tipo NOT IN
       ('debito', 'credito', 'receita', 'transferencia', 'investimento', 'rendimento') THEN
        PERFORM abako_erro('AB422', 'tipo de lançamento inválido');
    END IF;
    IF p_data IS NULL OR p_data < DATE '2000-01-01' OR p_data > v_hoje THEN
        PERFORM abako_erro('AB422', 'a data precisa estar entre 2000 e hoje');
    END IF;
    IF v_descricao IS NOT NULL AND length(v_descricao) > 200 THEN
        PERFORM abako_erro('AB422', 'a descrição passa de 200 caracteres');
    END IF;
    IF p_tipo = 'credito' THEN
        IF p_parcelas IS NULL OR p_parcelas < 1 OR p_parcelas > 48 THEN
            PERFORM abako_erro('AB422', 'o número de parcelas vai de 1 a 48');
        END IF;
    ELSIF p_parcelas IS NOT NULL THEN
        PERFORM abako_erro('AB422', 'parcelas são só da compra a crédito');
    END IF;

    IF p_tipo = 'rendimento' THEN
        IF p_valor IS NOT NULL THEN
            PERFORM abako_erro('AB422',
                'no rendimento informe bruto e imposto; o valor sai da conta');
        END IF;
        IF p_bruto IS NULL OR p_imposto IS NULL OR p_bruto <= 0 OR p_imposto < 0
           OR p_imposto >= p_bruto OR p_bruto <> round(p_bruto, 2)
           OR p_imposto <> round(p_imposto, 2) THEN
            PERFORM abako_erro('AB422',
                'rendimento precisa de bruto > 0 e imposto entre 0 e o bruto');
        END IF;
        v_valor := p_bruto - p_imposto;
    ELSE
        IF p_bruto IS NOT NULL OR p_imposto IS NOT NULL THEN
            PERFORM abako_erro('AB422', 'bruto e imposto são só do rendimento');
        END IF;
        IF p_valor IS NULL OR p_valor <= 0 OR p_valor <> round(p_valor, 2) THEN
            PERFORM abako_erro('AB422', 'o valor precisa ser positivo, com até 2 casas');
        END IF;
        v_valor := p_valor;
    END IF;
    IF p_tipo = 'credito' AND v_valor < p_parcelas * 0.01 THEN
        PERFORM abako_erro('AB422', 'cada parcela precisa valer ao menos 0,01');
    END IF;

    SELECT c.tipo INTO v_tipo_conta FROM conta_versao c
    WHERE c.user_id = p_user AND c.conta_id = p_conta AND c.vigente AND NOT c.excluida
    FOR SHARE;  -- a conta não muda de tipo enquanto este lançamento é gravado
    IF NOT FOUND THEN
        -- Uma edição da conta pode ter fechado a linha durante a espera: lê de novo.
        SELECT c.tipo INTO v_tipo_conta FROM conta_versao c
        WHERE c.user_id = p_user AND c.conta_id = p_conta AND c.vigente
          AND NOT c.excluida
        FOR SHARE;
        IF NOT FOUND THEN
            PERFORM abako_erro('AB404', 'conta não encontrada');
        END IF;
    END IF;

    IF p_tipo = 'credito' THEN
        IF v_tipo_conta <> 'divida' THEN
            PERFORM abako_erro('AB422', 'compra a crédito só em conta de cartão');
        END IF;
    ELSIF v_tipo_conta = 'divida' THEN
        -- O cartão só recebe compra a crédito e pagamento (transferência com destino nele).
        PERFORM abako_erro('AB422', 'a conta de cartão só recebe compra a crédito e pagamento');
    END IF;

    IF p_tipo IN ('transferencia', 'investimento') THEN
        IF p_conta_destino IS NULL THEN
            PERFORM abako_erro('AB422', 'informe a conta de destino');
        END IF;
        IF p_conta_destino = p_conta THEN
            PERFORM abako_erro('AB422', 'origem e destino precisam ser contas diferentes');
        END IF;
        SELECT c.tipo INTO v_tipo_destino FROM conta_versao c
        WHERE c.user_id = p_user AND c.conta_id = p_conta_destino AND c.vigente
          AND NOT c.excluida
        FOR SHARE;
        IF NOT FOUND THEN
            SELECT c.tipo INTO v_tipo_destino FROM conta_versao c
            WHERE c.user_id = p_user AND c.conta_id = p_conta_destino AND c.vigente
              AND NOT c.excluida
            FOR SHARE;
            IF NOT FOUND THEN
                PERFORM abako_erro('AB404', 'conta de destino não encontrada');
            END IF;
        END IF;
        IF v_tipo_conta = 'beneficio' OR v_tipo_destino = 'beneficio' THEN
            PERFORM abako_erro('AB422', 'transferência com conta de benefício ainda não');
        END IF;
        IF p_tipo = 'investimento' AND v_tipo_destino <> 'investimento' THEN
            PERFORM abako_erro('AB422', 'investimento vai para conta do tipo investimento');
        END IF;
    ELSE
        IF p_conta_destino IS NOT NULL THEN
            PERFORM abako_erro('AB422', 'conta de destino só em transferência');
        END IF;
        IF p_tipo = 'rendimento' AND v_tipo_conta = 'beneficio' THEN
            PERFORM abako_erro('AB422', 'rendimento não cai em conta de benefício');
        END IF;
    END IF;

    -- Competência da primeira parcela (mês do fechamento), gravada: na edição que não muda
    -- cartão nem data ela é mantida, mesmo que o fechamento tenha mudado depois (ADR 043).
    IF p_tipo = 'credito' THEN
        IF p_transacao IS NOT NULL THEN
            SELECT t.competencia, t.data_transacao, t.conta_id INTO v_ant
            FROM transacao_versao t
            WHERE t.user_id = p_user AND t.transacao_id = p_transacao AND t.versao = p_versao
              AND t.perna = 1 AND t.parcela = 1 AND t.tipo = 'credito' AND NOT t.excluida;
            IF FOUND AND v_ant.data_transacao = p_data AND v_ant.conta_id = p_conta THEN
                v_comp := v_ant.competencia;
            END IF;
        END IF;
        IF v_comp IS NULL THEN
            v_comp := competencia_compra(p_user, p_conta, p_data);
        END IF;
        IF v_comp IS NULL THEN
            PERFORM abako_erro('AB422', 'o cartão não tem fechamento vigente nessa data');
        END IF;
    END IF;

    IF p_transacao IS NULL THEN
        v_id := nextval('transacao_id_seq');
        v_versao := 1;
    ELSE
        -- Fecha a versão vigente (todas as pernas e parcelas) só se for a versão que o
        -- cliente leu.
        UPDATE transacao_versao t SET vigente = false
        WHERE t.user_id = p_user AND t.transacao_id = p_transacao AND t.vigente
          AND NOT t.excluida AND t.versao = p_versao;
        GET DIAGNOSTICS v_fechadas = ROW_COUNT;
        IF v_fechadas = 0 THEN
            IF EXISTS (SELECT 1 FROM transacao_versao t
                       WHERE t.user_id = p_user AND t.transacao_id = p_transacao
                         AND t.vigente AND NOT t.excluida) THEN
                PERFORM abako_erro('AB409', 'o lançamento mudou desde a última leitura');
            END IF;
            PERFORM abako_erro('AB404', 'lançamento não encontrado');
        END IF;
        v_id := p_transacao;
        v_versao := p_versao + 1;
    END IF;

    IF p_tipo = 'credito' THEN
        -- n-1 primeiras = total / n truncado em centavos; a última absorve o resto (INV-02).
        v_base := trunc(v_valor / p_parcelas, 2);
        INSERT INTO transacao_versao
            (user_id, transacao_id, versao, tipo, perna, parcela, conta_id, data_transacao,
             valor, descricao, competencia, chave_idempotencia, hash_corpo)
        SELECT p_user, v_id, v_versao, 'credito', 1, k, p_conta, p_data,
               -(CASE WHEN k < p_parcelas THEN v_base
                      ELSE v_valor - v_base * (p_parcelas - 1) END),
               v_descricao,
               to_char(to_date(v_comp || '-01', 'YYYY-MM-DD') + make_interval(months => k - 1),
                       'YYYY-MM'),
               CASE WHEN k = 1 AND v_versao = 1 THEN p_chave END,
               CASE WHEN k = 1 AND v_versao = 1 AND p_chave IS NOT NULL THEN p_hash END
        FROM generate_series(1, p_parcelas) AS k;
        RETURN QUERY SELECT v_id, v_versao, true;
        RETURN;
    END IF;

    INSERT INTO transacao_versao
        (user_id, transacao_id, versao, tipo, perna, conta_id, data_transacao, valor,
         bruto, imposto, descricao, chave_idempotencia, hash_corpo)
    VALUES (p_user, v_id, v_versao, p_tipo, 1, p_conta, p_data,
            CASE WHEN p_tipo IN ('debito', 'transferencia', 'investimento')
                 THEN -v_valor ELSE v_valor END,
            CASE WHEN p_tipo = 'rendimento' THEN p_bruto END,
            CASE WHEN p_tipo = 'rendimento' THEN p_imposto END,
            v_descricao,
            CASE WHEN v_versao = 1 THEN p_chave END,
            CASE WHEN v_versao = 1 AND p_chave IS NOT NULL THEN p_hash END);
    IF p_tipo IN ('transferencia', 'investimento') THEN
        INSERT INTO transacao_versao
            (user_id, transacao_id, versao, tipo, perna, conta_id, data_transacao, valor,
             descricao)
        VALUES (p_user, v_id, v_versao, p_tipo, 2, p_conta_destino, p_data, v_valor,
                v_descricao);
    END IF;
    RETURN QUERY SELECT v_id, v_versao, true;
END
$$
"""

SQL_LANCAMENTO_EXCLUIR = """
CREATE OR REPLACE FUNCTION lancamento_excluir(p_user bigint, p_transacao bigint, p_versao integer)
RETURNS integer
LANGUAGE plpgsql SECURITY DEFINER SET search_path = public, pg_temp AS $$
DECLARE
    v_fechadas integer;
BEGIN
    UPDATE transacao_versao t SET vigente = false
    WHERE t.user_id = p_user AND t.transacao_id = p_transacao AND t.vigente
      AND NOT t.excluida AND t.versao = p_versao;
    GET DIAGNOSTICS v_fechadas = ROW_COUNT;
    IF v_fechadas = 0 THEN
        IF EXISTS (SELECT 1 FROM transacao_versao t
                   WHERE t.user_id = p_user AND t.transacao_id = p_transacao
                     AND t.vigente AND NOT t.excluida) THEN
            PERFORM abako_erro('AB409', 'o lançamento mudou desde a última leitura');
        END IF;
        PERFORM abako_erro('AB404', 'lançamento não encontrado');
    END IF;
    -- Exclusão lógica: nova versão vigente marcada como excluída, cópia da anterior (todas as
    -- pernas e parcelas, com a competência gravada).
    INSERT INTO transacao_versao
        (user_id, transacao_id, versao, vigente, excluida, tipo, perna, parcela, conta_id,
         data_transacao, valor, bruto, imposto, descricao, competencia)
    SELECT t.user_id, t.transacao_id, p_versao + 1, true, true, t.tipo, t.perna, t.parcela,
           t.conta_id, t.data_transacao, t.valor, t.bruto, t.imposto, t.descricao,
           t.competencia
    FROM transacao_versao t
    WHERE t.user_id = p_user AND t.transacao_id = p_transacao AND t.versao = p_versao;
    RETURN p_versao + 1;
END
$$
"""

SQL_PERNAS_CK = """
CREATE OR REPLACE FUNCTION transacao_pernas_ck() RETURNS trigger
LANGUAGE plpgsql SET search_path = public, pg_temp AS $$
DECLARE
    v RECORD;
BEGIN
    SELECT count(*) AS n,
           count(*) FILTER (WHERE t.perna = 1) AS n1,
           count(*) FILTER (WHERE t.perna = 2) AS n2,
           sum(t.valor) AS soma,
           count(DISTINCT t.conta_id) AS contas,
           count(DISTINCT t.tipo) AS tipos,
           count(DISTINCT t.excluida) AS exclusoes,
           count(DISTINCT t.data_transacao) AS datas,
           count(DISTINCT t.parcela) AS parcelas,
           max(t.parcela) AS ultima,
           min(t.tipo) AS tipo
    INTO v FROM transacao_versao t
    WHERE t.user_id = NEW.user_id AND t.transacao_id = NEW.transacao_id
      AND t.versao = NEW.versao;
    IF v.tipos <> 1 OR v.exclusoes <> 1 OR v.datas <> 1
       OR (v.tipo IN ('transferencia', 'investimento')
           AND (v.n <> 2 OR v.n1 <> 1 OR v.n2 <> 1 OR v.soma <> 0 OR v.contas <> 2))
       -- compra a crédito: parcelas 1..n sem buraco nem repetição, todas na mesma conta
       OR (v.tipo = 'credito'
           AND (v.n2 <> 0 OR v.contas <> 1 OR v.parcelas <> v.n OR v.ultima <> v.n))
       OR (v.tipo NOT IN ('transferencia', 'investimento', 'credito') AND v.n <> 1) THEN
        RAISE EXCEPTION USING ERRCODE = 'check_violation',
            MESSAGE = 'pernas do lançamento inconsistentes (INV-01)';
    END IF;
    RETURN NULL;
END
$$
"""

SQL_FATURA_ITENS = """
CREATE FUNCTION fatura_itens(p_user bigint, p_conta bigint, p_competencia text)
RETURNS TABLE (
    transacao_id bigint, versao integer, parcela integer, parcelas integer,
    data_compra date, valor numeric, descricao text
)
LANGUAGE sql STABLE AS $$
    SELECT x.transacao_id, x.versao, x.parcela::int, x.n::int, x.data_transacao,
           -x.valor, x.descricao
    FROM (
        SELECT t.transacao_id, t.versao, t.parcela, t.data_transacao, t.valor, t.descricao,
               t.competencia, count(*) OVER (PARTITION BY t.transacao_id) AS n
        FROM transacao_vigente t
        WHERE t.user_id = p_user AND t.conta_id = p_conta AND t.tipo = 'credito'
    ) x
    WHERE x.competencia = p_competencia
    ORDER BY x.data_transacao, x.transacao_id, x.parcela
$$
"""

SQL_FATURA_TOTAL = """
CREATE FUNCTION fatura_total(p_user bigint, p_conta bigint, p_competencia text)
RETURNS numeric
LANGUAGE sql STABLE AS $$
    SELECT COALESCE(sum(-t.valor), 0)
    FROM transacao_vigente t
    WHERE t.user_id = p_user AND t.conta_id = p_conta AND t.tipo = 'credito'
      AND t.competencia = p_competencia
$$
"""

SQL_LIMITE_LINHA = """
CREATE FUNCTION limite_linha(p_user bigint, p_linha bigint, p_em date DEFAULT NULL)
RETURNS TABLE (limite numeric, usado numeric, disponivel numeric)
LANGUAGE sql STABLE AS $$
    WITH l AS (
        SELECT v.limite FROM linha_credito v
        WHERE v.user_id = p_user AND v.linha_id = p_linha AND v.vigente AND NOT v.excluida
    ),
    u AS (
        SELECT -COALESCE(sum(saldo_derivado(
                   p_user, c.conta_id,
                   COALESCE(p_em, (now() AT TIME ZONE 'America/Sao_Paulo')::date))), 0) AS usado
        FROM conta_versao c
        WHERE c.user_id = p_user AND c.linha_credito_id = p_linha AND c.tipo = 'divida'
          AND c.vigente AND NOT c.excluida
    )
    SELECT l.limite, u.usado, l.limite - u.usado FROM l, u
$$
"""

# ---------------------------------------------------------------------------------------------
# Definições da 0005 (restauradas no downgrade)
# ---------------------------------------------------------------------------------------------

ANTIGA_CONTA_GRAVAR = """
CREATE FUNCTION conta_gravar(
    p_user bigint, p_conta bigint, p_versao integer,
    p_nome text, p_tipo text, p_conta_mae bigint
)
RETURNS TABLE (conta_id bigint, versao integer)
LANGUAGE plpgsql SECURITY DEFINER SET search_path = public, pg_temp AS $$
DECLARE
    v_nome text := btrim(coalesce(p_nome, ''));
    v_atual conta_versao%ROWTYPE;
    v_id bigint;
    v_versao integer;
BEGIN
    IF v_nome = '' OR length(v_nome) > 80 THEN
        PERFORM abako_erro('AB422', 'o nome precisa ter de 1 a 80 caracteres');
    END IF;
    IF p_tipo IS NULL OR p_tipo NOT IN ('corrente', 'reserva', 'investimento', 'beneficio')
    THEN
        PERFORM abako_erro('AB422', 'tipo de conta inválido');
    END IF;
    IF p_conta_mae IS NOT NULL THEN
        IF p_tipo NOT IN ('reserva', 'investimento') THEN
            PERFORM abako_erro('AB422',
                'só reserva ou investimento pertence a outra conta');
        END IF;
        -- FOR SHARE: o banco não deixa de ser corrente enquanto esta conta é gravada.
        PERFORM 1 FROM conta_versao c
        WHERE c.user_id = p_user AND c.conta_id = p_conta_mae
          AND c.vigente AND NOT c.excluida AND c.tipo = 'corrente'
        FOR SHARE;
        IF p_conta_mae IS NOT DISTINCT FROM p_conta OR NOT FOUND THEN
            PERFORM abako_erro('AB422', 'a conta do banco precisa ser uma conta corrente');
        END IF;
    END IF;

    IF p_conta IS NULL THEN
        v_id := nextval('conta_id_seq');
        v_versao := 1;
    ELSE
        IF p_versao IS NULL THEN
            PERFORM abako_erro('AB422', 'editar conta exige a versão lida');
        END IF;
        SELECT * INTO v_atual FROM conta_versao c
        WHERE c.user_id = p_user AND c.conta_id = p_conta AND c.vigente
          AND NOT c.excluida
        FOR UPDATE;
        IF NOT FOUND THEN
            -- Outra edição pode ter fechado a linha enquanto esta esperava a trava: a
            -- conta existe, só mudou (INV-29). Uma nova leitura já vê a versão nova.
            IF EXISTS (SELECT 1 FROM conta_versao c
                       WHERE c.user_id = p_user AND c.conta_id = p_conta
                         AND c.vigente AND NOT c.excluida) THEN
                PERFORM abako_erro('AB409', 'a conta mudou desde a última leitura');
            END IF;
            PERFORM abako_erro('AB404', 'conta não encontrada');
        END IF;
        IF v_atual.versao IS DISTINCT FROM p_versao THEN
            PERFORM abako_erro('AB409', 'a conta mudou desde a última leitura');
        END IF;
        IF v_atual.tipo <> p_tipo THEN
            IF (v_atual.tipo = 'beneficio' OR p_tipo = 'beneficio') AND EXISTS (
                SELECT 1 FROM transacao_versao t
                WHERE t.user_id = p_user AND t.conta_id = p_conta
                  AND t.vigente AND NOT t.excluida
            ) THEN
                PERFORM abako_erro('AB422',
                    'conta com lançamentos não entra nem sai do tipo benefício');
            END IF;
            IF v_atual.tipo = 'investimento' AND EXISTS (
                SELECT 1 FROM transacao_versao t
                WHERE t.user_id = p_user AND t.conta_id = p_conta AND t.perna = 2
                  AND t.tipo = 'investimento' AND t.vigente AND NOT t.excluida
            ) THEN
                PERFORM abako_erro('AB422',
                    'conta que recebeu investimento continua do tipo investimento');
            END IF;
            IF v_atual.tipo = 'corrente' AND EXISTS (
                SELECT 1 FROM conta_versao c
                WHERE c.user_id = p_user AND c.conta_mae_id = p_conta
                  AND c.vigente AND NOT c.excluida
            ) THEN
                PERFORM abako_erro('AB422',
                    'esta conta tem reserva ou investimento ligado a ela');
            END IF;
        END IF;
        UPDATE conta_versao c SET vigente = false WHERE c.id = v_atual.id;
        v_id := p_conta;
        v_versao := v_atual.versao + 1;
    END IF;

    BEGIN
        INSERT INTO conta_versao
            (user_id, conta_id, versao, nome, tipo, conta_beneficio, conta_mae_id)
        VALUES (p_user, v_id, v_versao, v_nome, p_tipo, p_tipo = 'beneficio',
                p_conta_mae);
    EXCEPTION WHEN unique_violation THEN
        PERFORM abako_erro('AB410', 'já existe uma conta com esse nome');
    END;
    RETURN QUERY SELECT v_id, v_versao;
END
$$
"""

ANTIGA_LANCAMENTO_GRAVAR = """
CREATE FUNCTION lancamento_gravar(
    p_user bigint, p_transacao bigint, p_versao integer,
    p_tipo text, p_data date, p_valor numeric,
    p_conta bigint, p_conta_destino bigint,
    p_bruto numeric, p_imposto numeric, p_descricao text,
    p_chave text, p_hash text
)
RETURNS TABLE (transacao_id bigint, versao integer, criado boolean)
LANGUAGE plpgsql SECURITY DEFINER SET search_path = public, pg_temp AS $$
DECLARE
    v_hoje date := (now() AT TIME ZONE 'America/Sao_Paulo')::date;
    v_tipo_conta text;
    v_tipo_destino text;
    v_valor numeric;
    v_id bigint;
    v_versao integer;
    v_existente RECORD;
    v_fechadas integer;
    v_descricao text := nullif(btrim(p_descricao), '');
BEGIN
    -- Repetição da criação com a mesma chave (INV-28). A trava por (usuário, chave) faz
    -- a segunda requisição simultânea esperar a primeira terminar e então achar o
    -- lançamento dela, em vez de bater no índice único.
    IF p_transacao IS NULL AND p_chave IS NOT NULL THEN
        PERFORM pg_advisory_xact_lock(hashtextextended(p_user::text || ':' || p_chave, 0));
        SELECT t.transacao_id, t.hash_corpo INTO v_existente FROM transacao_versao t
        WHERE t.user_id = p_user AND t.chave_idempotencia = p_chave;
        IF FOUND THEN
            IF v_existente.hash_corpo IS DISTINCT FROM p_hash THEN
                PERFORM abako_erro('AB422', 'chave já usada com outros dados');
            END IF;
            RETURN QUERY
                SELECT t.transacao_id, t.versao, false FROM transacao_versao t
                WHERE t.user_id = p_user AND t.transacao_id = v_existente.transacao_id
                  AND t.vigente AND t.perna = 1;
            RETURN;
        END IF;
    END IF;

    IF p_tipo IN ('credito', 'repasse') THEN
        PERFORM abako_erro('AB422', 'esse tipo de lançamento ainda não está disponível');
    END IF;
    IF p_tipo IS NULL OR p_tipo NOT IN
       ('debito', 'receita', 'transferencia', 'investimento', 'rendimento') THEN
        PERFORM abako_erro('AB422', 'tipo de lançamento inválido');
    END IF;
    IF p_data IS NULL OR p_data < DATE '2000-01-01' OR p_data > v_hoje THEN
        PERFORM abako_erro('AB422', 'a data precisa estar entre 2000 e hoje');
    END IF;
    IF v_descricao IS NOT NULL AND length(v_descricao) > 200 THEN
        PERFORM abako_erro('AB422', 'a descrição passa de 200 caracteres');
    END IF;

    IF p_tipo = 'rendimento' THEN
        IF p_valor IS NOT NULL THEN
            PERFORM abako_erro('AB422',
                'no rendimento informe bruto e imposto; o valor sai da conta');
        END IF;
        IF p_bruto IS NULL OR p_imposto IS NULL OR p_bruto <= 0 OR p_imposto < 0
           OR p_imposto >= p_bruto OR p_bruto <> round(p_bruto, 2)
           OR p_imposto <> round(p_imposto, 2) THEN
            PERFORM abako_erro('AB422',
                'rendimento precisa de bruto > 0 e imposto entre 0 e o bruto');
        END IF;
        v_valor := p_bruto - p_imposto;
    ELSE
        IF p_bruto IS NOT NULL OR p_imposto IS NOT NULL THEN
            PERFORM abako_erro('AB422', 'bruto e imposto são só do rendimento');
        END IF;
        IF p_valor IS NULL OR p_valor <= 0 OR p_valor <> round(p_valor, 2) THEN
            PERFORM abako_erro('AB422', 'o valor precisa ser positivo, com até 2 casas');
        END IF;
        v_valor := p_valor;
    END IF;

    SELECT c.tipo INTO v_tipo_conta FROM conta_versao c
    WHERE c.user_id = p_user AND c.conta_id = p_conta AND c.vigente AND NOT c.excluida
    FOR SHARE;  -- a conta não muda de tipo enquanto este lançamento é gravado
    IF NOT FOUND THEN
        -- Uma edição da conta pode ter fechado a linha durante a espera: lê de novo.
        SELECT c.tipo INTO v_tipo_conta FROM conta_versao c
        WHERE c.user_id = p_user AND c.conta_id = p_conta AND c.vigente
          AND NOT c.excluida
        FOR SHARE;
        IF NOT FOUND THEN
            PERFORM abako_erro('AB404', 'conta não encontrada');
        END IF;
    END IF;

    IF p_tipo IN ('transferencia', 'investimento') THEN
        IF p_conta_destino IS NULL THEN
            PERFORM abako_erro('AB422', 'informe a conta de destino');
        END IF;
        IF p_conta_destino = p_conta THEN
            PERFORM abako_erro('AB422', 'origem e destino precisam ser contas diferentes');
        END IF;
        SELECT c.tipo INTO v_tipo_destino FROM conta_versao c
        WHERE c.user_id = p_user AND c.conta_id = p_conta_destino AND c.vigente
          AND NOT c.excluida
        FOR SHARE;
        IF NOT FOUND THEN
            SELECT c.tipo INTO v_tipo_destino FROM conta_versao c
            WHERE c.user_id = p_user AND c.conta_id = p_conta_destino AND c.vigente
              AND NOT c.excluida
            FOR SHARE;
            IF NOT FOUND THEN
                PERFORM abako_erro('AB404', 'conta de destino não encontrada');
            END IF;
        END IF;
        IF v_tipo_conta = 'beneficio' OR v_tipo_destino = 'beneficio' THEN
            PERFORM abako_erro('AB422', 'transferência com conta de benefício ainda não');
        END IF;
        IF p_tipo = 'investimento' AND v_tipo_destino <> 'investimento' THEN
            PERFORM abako_erro('AB422', 'investimento vai para conta do tipo investimento');
        END IF;
    ELSE
        IF p_conta_destino IS NOT NULL THEN
            PERFORM abako_erro('AB422', 'conta de destino só em transferência');
        END IF;
        IF p_tipo = 'rendimento' AND v_tipo_conta = 'beneficio' THEN
            PERFORM abako_erro('AB422', 'rendimento não cai em conta de benefício');
        END IF;
    END IF;

    IF p_transacao IS NULL THEN
        v_id := nextval('transacao_id_seq');
        v_versao := 1;
    ELSE
        -- Fecha a versão vigente (todas as pernas) só se for a versão que o cliente leu.
        UPDATE transacao_versao t SET vigente = false
        WHERE t.user_id = p_user AND t.transacao_id = p_transacao AND t.vigente
          AND NOT t.excluida AND t.versao = p_versao;
        GET DIAGNOSTICS v_fechadas = ROW_COUNT;
        IF v_fechadas = 0 THEN
            IF EXISTS (SELECT 1 FROM transacao_versao t
                       WHERE t.user_id = p_user AND t.transacao_id = p_transacao
                         AND t.vigente AND NOT t.excluida) THEN
                PERFORM abako_erro('AB409', 'o lançamento mudou desde a última leitura');
            END IF;
            PERFORM abako_erro('AB404', 'lançamento não encontrado');
        END IF;
        v_id := p_transacao;
        v_versao := p_versao + 1;
    END IF;

    INSERT INTO transacao_versao
        (user_id, transacao_id, versao, tipo, perna, conta_id, data_transacao, valor,
         bruto, imposto, descricao, chave_idempotencia, hash_corpo)
    VALUES (p_user, v_id, v_versao, p_tipo, 1, p_conta, p_data,
            CASE WHEN p_tipo IN ('debito', 'transferencia', 'investimento')
                 THEN -v_valor ELSE v_valor END,
            CASE WHEN p_tipo = 'rendimento' THEN p_bruto END,
            CASE WHEN p_tipo = 'rendimento' THEN p_imposto END,
            v_descricao,
            CASE WHEN v_versao = 1 THEN p_chave END,
            CASE WHEN v_versao = 1 AND p_chave IS NOT NULL THEN p_hash END);
    IF p_tipo IN ('transferencia', 'investimento') THEN
        INSERT INTO transacao_versao
            (user_id, transacao_id, versao, tipo, perna, conta_id, data_transacao, valor,
             descricao)
        VALUES (p_user, v_id, v_versao, p_tipo, 2, p_conta_destino, p_data, v_valor,
                v_descricao);
    END IF;
    RETURN QUERY SELECT v_id, v_versao, true;
END
$$
"""

ANTIGA_LANCAMENTO_EXCLUIR = """
CREATE OR REPLACE FUNCTION lancamento_excluir(p_user bigint, p_transacao bigint, p_versao integer)
RETURNS integer
LANGUAGE plpgsql SECURITY DEFINER SET search_path = public, pg_temp AS $$
DECLARE
    v_fechadas integer;
BEGIN
    UPDATE transacao_versao t SET vigente = false
    WHERE t.user_id = p_user AND t.transacao_id = p_transacao AND t.vigente
      AND NOT t.excluida AND t.versao = p_versao;
    GET DIAGNOSTICS v_fechadas = ROW_COUNT;
    IF v_fechadas = 0 THEN
        IF EXISTS (SELECT 1 FROM transacao_versao t
                   WHERE t.user_id = p_user AND t.transacao_id = p_transacao
                     AND t.vigente AND NOT t.excluida) THEN
            PERFORM abako_erro('AB409', 'o lançamento mudou desde a última leitura');
        END IF;
        PERFORM abako_erro('AB404', 'lançamento não encontrado');
    END IF;
    -- Exclusão lógica: nova versão vigente marcada como excluída, cópia da anterior.
    INSERT INTO transacao_versao
        (user_id, transacao_id, versao, vigente, excluida, tipo, perna, conta_id,
         data_transacao, valor, bruto, imposto, descricao)
    SELECT t.user_id, t.transacao_id, p_versao + 1, true, true, t.tipo, t.perna,
           t.conta_id, t.data_transacao, t.valor, t.bruto, t.imposto, t.descricao
    FROM transacao_versao t
    WHERE t.user_id = p_user AND t.transacao_id = p_transacao AND t.versao = p_versao;
    RETURN p_versao + 1;
END
$$
"""

ANTIGA_PERNAS_CK = """
CREATE OR REPLACE FUNCTION transacao_pernas_ck() RETURNS trigger
LANGUAGE plpgsql SET search_path = public, pg_temp AS $$
DECLARE
    v RECORD;
BEGIN
    SELECT count(*) AS n,
           count(*) FILTER (WHERE t.perna = 1) AS n1,
           count(*) FILTER (WHERE t.perna = 2) AS n2,
           sum(t.valor) AS soma,
           count(DISTINCT t.conta_id) AS contas,
           count(DISTINCT t.tipo) AS tipos,
           count(DISTINCT t.excluida) AS exclusoes,
           count(DISTINCT t.data_transacao) AS datas,
           min(t.tipo) AS tipo
    INTO v FROM transacao_versao t
    WHERE t.user_id = NEW.user_id AND t.transacao_id = NEW.transacao_id
      AND t.versao = NEW.versao;
    IF v.tipos <> 1 OR v.exclusoes <> 1 OR v.datas <> 1
       OR (v.tipo IN ('transferencia', 'investimento')
           AND (v.n <> 2 OR v.n1 <> 1 OR v.n2 <> 1 OR v.soma <> 0 OR v.contas <> 2))
       OR (v.tipo NOT IN ('transferencia', 'investimento') AND v.n <> 1) THEN
        RAISE EXCEPTION USING ERRCODE = 'check_violation',
            MESSAGE = 'pernas do lançamento inconsistentes (INV-01)';
    END IF;
    RETURN NULL;
END
$$
"""


def upgrade() -> None:
    # ---------- contas: tipo cartão e linha de crédito ----------
    op.execute("ALTER TABLE conta_versao DROP CONSTRAINT conta_versao_tipo_ck")
    op.execute(
        f"ALTER TABLE conta_versao ADD CONSTRAINT conta_versao_tipo_ck "
        f"CHECK (tipo IN ({TIPOS_CONTA}))"
    )
    op.execute("ALTER TABLE conta_versao ADD COLUMN linha_credito_id bigint")
    op.execute(
        "ALTER TABLE conta_versao ADD CONSTRAINT conta_versao_linha_ck "
        "CHECK ((tipo = 'divida') = (linha_credito_id IS NOT NULL))"
    )

    op.execute("CREATE SEQUENCE linha_credito_id_seq")
    op.execute(
        """
        CREATE TABLE linha_credito (
            id         bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
            user_id    bigint  NOT NULL REFERENCES usuario (user_id),
            linha_id   bigint  NOT NULL DEFAULT nextval('linha_credito_id_seq'),
            versao     integer NOT NULL DEFAULT 1 CHECK (versao >= 1),
            vigente    boolean NOT NULL DEFAULT true,
            excluida   boolean NOT NULL DEFAULT false,
            nome       text    NOT NULL,
            limite     numeric(14, 2) NOT NULL CHECK (limite >= 0),
            criado_em  timestamptz NOT NULL DEFAULT now(),
            UNIQUE (user_id, linha_id, versao)
        )
        """
    )
    op.execute(
        "CREATE UNIQUE INDEX linha_credito_vigente_uq ON linha_credito (user_id, linha_id) "
        "WHERE vigente"
    )
    op.execute(
        "CREATE UNIQUE INDEX linha_credito_nome_uq ON linha_credito (user_id, lower(nome)) "
        "WHERE vigente AND NOT excluida"
    )

    # Fechamento com vigência: append-only (como o snapshot). Para a mesma `vigente_desde`
    # vale o último registrado.
    op.execute(
        """
        CREATE TABLE cartao_fechamento (
            id            bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
            user_id       bigint   NOT NULL REFERENCES usuario (user_id),
            conta_id      bigint   NOT NULL,
            dia           smallint NOT NULL CHECK (dia BETWEEN 1 AND 31),
            vigente_desde date     NOT NULL,
            registrado_em timestamptz NOT NULL DEFAULT now()
        )
        """
    )
    op.execute(
        "CREATE INDEX cartao_fechamento_conta_idx ON cartao_fechamento "
        "(user_id, conta_id, vigente_desde, registrado_em)"
    )
    op.execute(
        """
        CREATE VIEW fechamento_vigente WITH (security_invoker = true) AS
        SELECT DISTINCT ON (user_id, conta_id, vigente_desde)
               id, user_id, conta_id, dia, vigente_desde, registrado_em
        FROM cartao_fechamento
        ORDER BY user_id, conta_id, vigente_desde, registrado_em DESC, id DESC
        """
    )

    # ---------- lançamentos: parcela e competência ----------
    op.execute(
        "ALTER TABLE transacao_versao ADD COLUMN parcela smallint NOT NULL DEFAULT 1 "
        "CHECK (parcela BETWEEN 1 AND 48)"
    )
    op.execute("ALTER TABLE transacao_versao ADD COLUMN competencia text")
    op.execute(
        "ALTER TABLE transacao_versao ADD CONSTRAINT transacao_versao_parcela_ck "
        "CHECK (parcela = 1 OR tipo = 'credito')"
    )
    op.execute(
        "ALTER TABLE transacao_versao ADD CONSTRAINT transacao_versao_competencia_ck CHECK ("
        "  CASE WHEN tipo = 'credito'"
        "       THEN coalesce(competencia ~ '^[0-9]{4}-(0[1-9]|1[0-2])$', false)"
        "       ELSE competencia IS NULL END)"
    )
    op.execute("ALTER TABLE transacao_versao DROP CONSTRAINT transacao_versao_sinal_ck")
    op.execute(
        "ALTER TABLE transacao_versao ADD CONSTRAINT transacao_versao_sinal_ck CHECK ("
        "     (tipo = 'debito' AND valor < 0)"
        "  OR (tipo = 'credito' AND valor < 0)"  # a dívida do cartão é negativa (ADR 043)
        "  OR (tipo = 'receita' AND valor > 0)"
        "  OR (tipo IN ('transferencia', 'investimento')"
        "      AND ((perna = 1 AND valor < 0) OR (perna = 2 AND valor > 0)))"
        "  OR (tipo = 'rendimento' AND valor > 0)"
        "  OR tipo = 'repasse')"  # regra própria na SPEC-007
    )
    # Unicidades e vigência passam a incluir a parcela.
    op.execute("ALTER TABLE transacao_versao DROP CONSTRAINT transacao_versao_id_versao_perna_key")
    op.execute(
        "ALTER TABLE transacao_versao ADD CONSTRAINT transacao_versao_id_versao_perna_key "
        "UNIQUE (user_id, transacao_id, versao, perna, parcela)"
    )
    op.execute("DROP INDEX transacao_versao_vigente_uq")
    op.execute(
        "CREATE UNIQUE INDEX transacao_versao_vigente_uq ON transacao_versao "
        "(user_id, transacao_id, perna, parcela) WHERE vigente"
    )
    op.execute("ALTER TABLE transacao_versao DROP CONSTRAINT transacao_versao_chave_ck")
    op.execute(
        "ALTER TABLE transacao_versao ADD CONSTRAINT transacao_versao_chave_ck "
        "CHECK (chave_idempotencia IS NULL OR (perna = 1 AND parcela = 1 AND versao = 1))"
    )
    op.execute(
        "CREATE INDEX transacao_versao_fatura_idx ON transacao_versao "
        "(user_id, conta_id, competencia) WHERE vigente AND NOT excluida AND tipo = 'credito'"
    )

    op.execute(
        """
        CREATE OR REPLACE VIEW transacao_vigente WITH (security_invoker = true) AS
        SELECT id, user_id, transacao_id, versao, conta_id, data_transacao, valor, descricao,
               tipo, perna, bruto, imposto, parcela, competencia
        FROM transacao_versao
        WHERE vigente AND NOT excluida
        """
    )
    # Um lançamento por linha; na compra a crédito o valor é o total das parcelas.
    op.execute("DROP VIEW lancamento_vigente")
    op.execute(
        """
        CREATE VIEW lancamento_vigente WITH (security_invoker = true) AS
        SELECT p1.user_id, p1.transacao_id, p1.versao, p1.tipo, p1.data_transacao,
               CASE WHEN p1.tipo = 'credito' THEN c.total ELSE abs(p1.valor) END AS valor,
               p1.conta_id, p2.conta_id AS conta_destino_id,
               p1.bruto, p1.imposto, p1.descricao, p1.criado_em,
               c.parcelas, p1.competencia
        FROM transacao_versao p1
        LEFT JOIN transacao_versao p2
               ON p2.user_id = p1.user_id AND p2.transacao_id = p1.transacao_id
              AND p2.versao = p1.versao AND p2.perna = 2
        LEFT JOIN LATERAL (
            SELECT count(*)::int AS parcelas, -sum(x.valor) AS total
            FROM transacao_versao x
            WHERE x.user_id = p1.user_id AND x.transacao_id = p1.transacao_id
              AND x.versao = p1.versao AND x.perna = 1
        ) c ON p1.tipo = 'credito'
        WHERE p1.perna = 1 AND p1.parcela = 1 AND p1.vigente AND NOT p1.excluida
        """
    )

    # ---------- funções ----------
    op.execute(f"DROP FUNCTION {ASSIN_CONTA_ANTIGA}")
    op.execute(f"DROP FUNCTION {ASSIN_LANC_ANTIGA}")
    op.execute(SQL_CONTA_GRAVAR)
    op.execute(SQL_LINHA_GRAVAR)
    op.execute(SQL_FECHAMENTO_GRAVAR)
    op.execute(SQL_FECHAMENTO_EFETIVO)
    op.execute(SQL_COMPETENCIA_COMPRA)
    op.execute(SQL_LANCAMENTO_GRAVAR)
    op.execute(SQL_LANCAMENTO_EXCLUIR)
    op.execute(SQL_PERNAS_CK)
    op.execute(SQL_FATURA_ITENS)
    op.execute(SQL_FATURA_TOTAL)
    op.execute(SQL_LIMITE_LINHA)

    # ---------- papéis ----------
    op.execute("GRANT SELECT ON linha_credito, cartao_fechamento TO abako_app, abako_pipeline")
    op.execute(
        "GRANT SELECT ON fechamento_vigente, lancamento_vigente TO abako_app, abako_pipeline"
    )
    for assinatura in (ASSIN_CONTA_NOVA, ASSIN_LANC_NOVA, *FUNCOES_NOVAS):
        op.execute(f"REVOKE ALL ON FUNCTION {assinatura} FROM PUBLIC")
        op.execute(f"GRANT EXECUTE ON FUNCTION {assinatura} TO abako_app")


def downgrade() -> None:
    # Irreversível com dados (ADR 043): voltar apagaria o cartão, as parcelas e a linha de
    # crédito. Com dado assim, o caminho é restaurar o backup anterior à 0006.
    op.execute(
        """
        DO $$
        BEGIN
            IF EXISTS (SELECT 1 FROM conta_versao WHERE tipo = 'divida')
               OR EXISTS (SELECT 1 FROM transacao_versao WHERE tipo = 'credito')
               OR EXISTS (SELECT 1 FROM linha_credito)
               OR EXISTS (SELECT 1 FROM cartao_fechamento)
            THEN
                RAISE EXCEPTION USING MESSAGE =
                    '0006: há cartão, compra a crédito, linha de crédito ou fechamento que só '
                    'existem nesta versão; o downgrade apagaria dados. Restaure o backup '
                    'anterior à 0006 (ADR 043).';
            END IF;
        END $$
        """
    )
    for assinatura in (
        "limite_linha(bigint, bigint, date)",
        "fatura_total(bigint, bigint, text)",
        "fatura_itens(bigint, bigint, text)",
    ):
        op.execute(f"DROP FUNCTION {assinatura}")
    op.execute(ANTIGA_PERNAS_CK)
    op.execute(ANTIGA_LANCAMENTO_EXCLUIR)
    op.execute(f"DROP FUNCTION {ASSIN_LANC_NOVA}")
    op.execute("DROP FUNCTION competencia_compra(bigint, bigint, date)")
    op.execute("DROP FUNCTION fechamento_efetivo(integer, date)")
    op.execute("DROP FUNCTION fechamento_gravar(bigint, bigint, integer, date)")
    op.execute("DROP FUNCTION linha_credito_gravar(bigint, bigint, integer, text, numeric)")
    op.execute(f"DROP FUNCTION {ASSIN_CONTA_NOVA}")
    op.execute(ANTIGA_CONTA_GRAVAR)
    op.execute(ANTIGA_LANCAMENTO_GRAVAR)
    for assinatura in (ASSIN_CONTA_ANTIGA, ASSIN_LANC_ANTIGA):
        op.execute(f"REVOKE ALL ON FUNCTION {assinatura} FROM PUBLIC")
        op.execute(f"GRANT EXECUTE ON FUNCTION {assinatura} TO abako_app")

    op.execute("DROP VIEW lancamento_vigente")
    op.execute(
        """
        CREATE VIEW lancamento_vigente WITH (security_invoker = true) AS
        SELECT p1.user_id, p1.transacao_id, p1.versao, p1.tipo, p1.data_transacao,
               abs(p1.valor) AS valor, p1.conta_id, p2.conta_id AS conta_destino_id,
               p1.bruto, p1.imposto, p1.descricao, p1.criado_em
        FROM transacao_versao p1
        LEFT JOIN transacao_versao p2
               ON p2.user_id = p1.user_id AND p2.transacao_id = p1.transacao_id
              AND p2.versao = p1.versao AND p2.perna = 2
        WHERE p1.perna = 1 AND p1.vigente AND NOT p1.excluida
        """
    )
    op.execute("DROP VIEW transacao_vigente")
    op.execute(
        """
        CREATE VIEW transacao_vigente WITH (security_invoker = true) AS
        SELECT id, user_id, transacao_id, versao, conta_id, data_transacao, valor, descricao,
               tipo, perna, bruto, imposto
        FROM transacao_versao
        WHERE vigente AND NOT excluida
        """
    )
    op.execute("GRANT SELECT ON lancamento_vigente, transacao_vigente TO abako_app, abako_pipeline")

    op.execute("DROP INDEX transacao_versao_fatura_idx")
    op.execute("ALTER TABLE transacao_versao DROP CONSTRAINT transacao_versao_chave_ck")
    op.execute(
        "ALTER TABLE transacao_versao ADD CONSTRAINT transacao_versao_chave_ck "
        "CHECK (chave_idempotencia IS NULL OR (perna = 1 AND versao = 1))"
    )
    op.execute("DROP INDEX transacao_versao_vigente_uq")
    op.execute(
        "CREATE UNIQUE INDEX transacao_versao_vigente_uq ON transacao_versao "
        "(user_id, transacao_id, perna) WHERE vigente"
    )
    op.execute("ALTER TABLE transacao_versao DROP CONSTRAINT transacao_versao_id_versao_perna_key")
    op.execute(
        "ALTER TABLE transacao_versao ADD CONSTRAINT transacao_versao_id_versao_perna_key "
        "UNIQUE (user_id, transacao_id, versao, perna)"
    )
    op.execute("ALTER TABLE transacao_versao DROP CONSTRAINT transacao_versao_sinal_ck")
    op.execute(
        "ALTER TABLE transacao_versao ADD CONSTRAINT transacao_versao_sinal_ck CHECK ("
        "     (tipo = 'debito' AND valor < 0)"
        "  OR (tipo = 'receita' AND valor > 0)"
        "  OR (tipo IN ('transferencia', 'investimento')"
        "      AND ((perna = 1 AND valor < 0) OR (perna = 2 AND valor > 0)))"
        "  OR (tipo = 'rendimento' AND valor > 0)"
        "  OR tipo IN ('credito', 'repasse'))"
    )
    op.execute("ALTER TABLE transacao_versao DROP CONSTRAINT transacao_versao_competencia_ck")
    op.execute("ALTER TABLE transacao_versao DROP CONSTRAINT transacao_versao_parcela_ck")
    op.execute("ALTER TABLE transacao_versao DROP COLUMN competencia")
    op.execute("ALTER TABLE transacao_versao DROP COLUMN parcela")

    op.execute("DROP VIEW fechamento_vigente")
    op.execute("DROP TABLE cartao_fechamento")
    op.execute("ALTER TABLE conta_versao DROP CONSTRAINT conta_versao_linha_ck")
    op.execute("ALTER TABLE conta_versao DROP COLUMN linha_credito_id")
    op.execute("DROP TABLE linha_credito")
    op.execute("DROP SEQUENCE linha_credito_id_seq")
    op.execute("ALTER TABLE conta_versao DROP CONSTRAINT conta_versao_tipo_ck")
    op.execute(
        f"ALTER TABLE conta_versao ADD CONSTRAINT conta_versao_tipo_ck "
        f"CHECK (tipo IN ({TIPOS_CONTA_ANTIGOS}))"
    )
