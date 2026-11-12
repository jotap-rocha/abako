"""terceiros, repasse e "a receber" por pessoa (SPEC-007, ADR 045)

Revision ID: 0008
Revises: 0007

SQL puro (ADR 025). A regra vive no banco (ADR 015):

- Tabela `pessoa` (cadastro mínimo, versionada como as demais entidades: `vigente`, `excluida`).
  O nome é dado pessoal: só existe aqui; o papel do pipeline não tem SELECT nessa coluna.
- `transacao_versao.pessoa_id` (sem chave estrangeira, como `conta_id`): a compra a crédito de
  terceiro aponta para a pessoa; nula = própria. O repasse exige pessoa. Os demais tipos não têm.
  Todas as parcelas de uma compra têm a mesma pessoa (gatilho de pernas): divisão é impossível.
- Tipo `repasse` passa a ser aceito: valor positivo, entrada em conta corrente, com pessoa. Não é
  receita nem gasto. A conta de benefício, reserva, investimento e cartão não recebem repasse.
- `lancamento_gravar` ganha o 15º parâmetro `p_pessoa bigint DEFAULT NULL`; quem chamava com 14
  argumentos continua funcionando. A função interna `lancamento_gravar_base` ganha o mesmo
  parâmetro; o guarda do estorno (0007) segue na frente. `lancamento_excluir_base` copia a pessoa.
- Leituras (nunca gravadas): `a_receber_pessoas` (D, R, a_receber, credito_da_pessoa),
  `fatura_resumo` (total, própria, terceiros) e `fatura_itens` com `pessoa_id` no fim. O crédito do
  estorno aparece na fatura no grupo da compra estornada (ADR 045 item 8).
- Views ganham `pessoa_id` no fim (a `parcela_ativa` é a fonte do gasto real, SPEC-008).
- Escrita só por funções SECURITY DEFINER (`pessoa_gravar`, `pessoa_excluir`, `lancamento_*`).
  Mensagens de erro são literais: nunca interpolam nome, valor ou id.
"""

from __future__ import annotations

import importlib.util
from pathlib import Path
from types import ModuleType

from alembic import op

revision = "0008"
down_revision = "0007"
branch_labels = None
depends_on = None

ASSIN_LANC_ANTIGA = (
    "lancamento_gravar(bigint, bigint, integer, text, date, numeric, bigint, bigint, "
    "numeric, numeric, text, text, text, integer)"
)
ASSIN_LANC = (
    "lancamento_gravar(bigint, bigint, integer, text, date, numeric, bigint, bigint, "
    "numeric, numeric, text, text, text, integer, bigint)"
)
ASSIN_LANC_BASE_ANTIGA = ASSIN_LANC_ANTIGA.replace("lancamento_gravar(", "lancamento_gravar_base(")
ASSIN_LANC_BASE = ASSIN_LANC.replace("lancamento_gravar(", "lancamento_gravar_base(")
ASSIN_EXCL_BASE = "lancamento_excluir_base(bigint, bigint, integer)"
ASSIN_FATURA_ITENS = "fatura_itens(bigint, bigint, text)"

FUNCOES_APP = (
    "pessoa_gravar(bigint, bigint, integer, text)",
    "pessoa_excluir(bigint, bigint, integer)",
    "a_receber_pessoas(bigint, bigint)",
    "fatura_resumo(bigint, bigint, text)",
    ASSIN_FATURA_ITENS,
    ASSIN_LANC,
)
FUNCOES_NOVAS = (
    "pessoa_gravar(bigint, bigint, integer, text)",
    "pessoa_excluir(bigint, bigint, integer)",
    "a_receber_pessoas(bigint, bigint)",
    "fatura_resumo(bigint, bigint, text)",
)

# ---------------------------------------------------------------------------------------------
# Funções novas
# ---------------------------------------------------------------------------------------------

SQL_PESSOA_GRAVAR = """
CREATE FUNCTION pessoa_gravar(
    p_user bigint, p_pessoa bigint, p_versao integer, p_nome text
)
RETURNS TABLE (pessoa_id bigint, versao integer)
LANGUAGE plpgsql SECURITY DEFINER SET search_path = public, pg_temp AS $$
DECLARE
    v_nome text := btrim(coalesce(p_nome, ''));
    v_atual pessoa%ROWTYPE;
    v_id bigint;
    v_versao integer;
BEGIN
    IF v_nome = '' OR length(v_nome) > 80 THEN
        PERFORM abako_erro('AB422', 'o nome precisa ter de 1 a 80 caracteres');
    END IF;
    IF p_pessoa IS NULL THEN
        v_id := nextval('pessoa_id_seq');
        v_versao := 1;
    ELSE
        IF p_versao IS NULL THEN
            PERFORM abako_erro('AB422', 'editar a pessoa exige a versão lida');
        END IF;
        SELECT * INTO v_atual FROM pessoa p
        WHERE p.user_id = p_user AND p.pessoa_id = p_pessoa AND p.vigente AND NOT p.excluida
        FOR UPDATE;
        IF NOT FOUND THEN
            -- Outra edição pode ter fechado a linha durante a espera: a pessoa existe, só mudou.
            IF EXISTS (SELECT 1 FROM pessoa p
                       WHERE p.user_id = p_user AND p.pessoa_id = p_pessoa
                         AND p.vigente AND NOT p.excluida) THEN
                PERFORM abako_erro('AB409', 'a pessoa mudou desde a última leitura');
            END IF;
            PERFORM abako_erro('AB404', 'pessoa não encontrada');
        END IF;
        IF v_atual.versao IS DISTINCT FROM p_versao THEN
            PERFORM abako_erro('AB409', 'a pessoa mudou desde a última leitura');
        END IF;
        UPDATE pessoa p SET vigente = false WHERE p.id = v_atual.id;
        v_id := p_pessoa;
        v_versao := v_atual.versao + 1;
    END IF;
    BEGIN
        INSERT INTO pessoa (user_id, pessoa_id, versao, nome)
        VALUES (p_user, v_id, v_versao, v_nome);
    EXCEPTION WHEN unique_violation THEN
        PERFORM abako_erro('AB410', 'já existe uma pessoa com esse nome');
    END;
    RETURN QUERY SELECT v_id, v_versao;
END
$$
"""

SQL_PESSOA_EXCLUIR = """
CREATE FUNCTION pessoa_excluir(p_user bigint, p_pessoa bigint, p_versao integer)
RETURNS integer
LANGUAGE plpgsql SECURITY DEFINER SET search_path = public, pg_temp AS $$
DECLARE
    v_atual pessoa%ROWTYPE;
BEGIN
    SELECT * INTO v_atual FROM pessoa p
    WHERE p.user_id = p_user AND p.pessoa_id = p_pessoa AND p.vigente AND NOT p.excluida
    FOR UPDATE;
    IF NOT FOUND THEN
        PERFORM abako_erro('AB404', 'pessoa não encontrada');
    END IF;
    IF v_atual.versao IS DISTINCT FROM p_versao THEN
        PERFORM abako_erro('AB409', 'a pessoa mudou desde a última leitura');
    END IF;
    -- O lançamento que aponta para a pessoa a trava com FOR SHARE antes de gravar: ou ele já
    -- está visível aqui, ou espera esta exclusão e então não acha a pessoa.
    IF EXISTS (SELECT 1 FROM transacao_vigente t
               WHERE t.user_id = p_user AND t.pessoa_id = p_pessoa) THEN
        PERFORM abako_erro('AB422',
            'a pessoa tem compras ou repasses e não pode ser excluída');
    END IF;
    UPDATE pessoa p SET vigente = false WHERE p.id = v_atual.id;
    INSERT INTO pessoa (user_id, pessoa_id, versao, vigente, excluida, nome)
    VALUES (p_user, p_pessoa, p_versao + 1, true, true, v_atual.nome);
    RETURN p_versao + 1;
END
$$
"""

# D = total das compras de terceiro (parcelas futuras, sem as estornadas); R = repasses.
# Só ids: o nome da pessoa é resolvido na borda da API.
SQL_A_RECEBER = """
CREATE FUNCTION a_receber_pessoas(p_user bigint, p_pessoa bigint DEFAULT NULL)
RETURNS TABLE (
    pessoa_id bigint, divida numeric, repassado numeric, a_receber numeric,
    credito_da_pessoa numeric
)
LANGUAGE sql STABLE AS $$
    WITH p AS (
        SELECT v.pessoa_id FROM pessoa v
        WHERE v.user_id = p_user AND v.vigente AND NOT v.excluida
          AND (p_pessoa IS NULL OR v.pessoa_id = p_pessoa)
    ),
    d AS (
        SELECT a.pessoa_id, -sum(a.valor) AS divida
        FROM parcela_ativa a
        WHERE a.user_id = p_user AND a.pessoa_id IS NOT NULL
        GROUP BY a.pessoa_id
    ),
    r AS (
        SELECT t.pessoa_id, sum(t.valor) AS repassado
        FROM transacao_vigente t
        WHERE t.user_id = p_user AND t.tipo = 'repasse'
        GROUP BY t.pessoa_id
    )
    SELECT p.pessoa_id,
           COALESCE(d.divida, 0.00),
           COALESCE(r.repassado, 0.00),
           greatest(COALESCE(d.divida, 0.00) - COALESCE(r.repassado, 0.00), 0.00),
           greatest(COALESCE(r.repassado, 0.00) - COALESCE(d.divida, 0.00), 0.00)
    FROM p
    LEFT JOIN d ON d.pessoa_id = p.pessoa_id
    LEFT JOIN r ON r.pessoa_id = p.pessoa_id
    ORDER BY p.pessoa_id
$$
"""

# Fatura: itens com a pessoa (nula = própria). O crédito do estorno herda a pessoa da compra.
SQL_FATURA_ITENS = """
CREATE FUNCTION fatura_itens(p_user bigint, p_conta bigint, p_competencia text)
RETURNS TABLE (
    transacao_id bigint, versao integer, parcela integer, parcelas integer,
    data_compra date, valor numeric, descricao text, pessoa_id bigint
)
LANGUAGE sql STABLE AS $$
    SELECT u.transacao_id, u.versao, u.parcela, u.parcelas, u.data_compra, u.valor,
           u.descricao, u.pessoa_id
    FROM (
        SELECT x.transacao_id, x.versao, x.parcela::int AS parcela, x.n::int AS parcelas,
               x.data_transacao AS data_compra, -x.valor AS valor, x.descricao, x.pessoa_id
        FROM (
            SELECT t.transacao_id, t.versao, t.parcela, t.data_transacao, t.valor, t.descricao,
                   t.competencia, t.parcelas AS n, t.pessoa_id
            FROM parcela_fatura t
            WHERE t.user_id = p_user AND t.conta_id = p_conta
        ) x
        WHERE x.competencia = p_competencia
        UNION ALL
        SELECT e.transacao_id, e.versao, 1, 1, e.data_transacao, -e.estorno_credito, e.descricao,
               (SELECT c.pessoa_id FROM transacao_vigente c
                WHERE c.user_id = e.user_id AND c.transacao_id = e.estorno_de
                  AND c.tipo = 'credito' AND c.parcela = 1)
        FROM transacao_vigente e
        WHERE e.user_id = p_user AND e.conta_id = p_conta AND e.tipo = 'estorno'
          AND e.competencia = p_competencia AND e.estorno_credito > 0
    ) u
    ORDER BY u.data_compra, u.transacao_id, u.parcela
$$
"""

SQL_FATURA_RESUMO = """
CREATE FUNCTION fatura_resumo(p_user bigint, p_conta bigint, p_competencia text)
RETURNS TABLE (total numeric, propria numeric, terceiros numeric)
LANGUAGE sql STABLE AS $$
    SELECT COALESCE(sum(i.valor), 0.00),
           COALESCE(sum(i.valor) FILTER (WHERE i.pessoa_id IS NULL), 0.00),
           COALESCE(sum(i.valor) FILTER (WHERE i.pessoa_id IS NOT NULL), 0.00)
    FROM fatura_itens(p_user, p_conta, p_competencia) i
$$
"""

# Uma pessoa por compra: todas as parcelas da versão têm a mesma (a ausência conta como uma).
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
           count(DISTINCT coalesce(t.pessoa_id, 0)) AS pessoas,
           max(t.parcela) AS ultima,
           min(t.tipo) AS tipo
    INTO v FROM transacao_versao t
    WHERE t.user_id = NEW.user_id AND t.transacao_id = NEW.transacao_id
      AND t.versao = NEW.versao;
    IF v.tipos <> 1 OR v.exclusoes <> 1 OR v.datas <> 1 OR v.pessoas <> 1
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

SQL_LANCAMENTO_EXCLUIR_BASE = """
CREATE OR REPLACE FUNCTION lancamento_excluir_base(
    p_user bigint, p_transacao bigint, p_versao integer
)
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
    -- pernas e parcelas, com a competência e a pessoa gravadas).
    INSERT INTO transacao_versao
        (user_id, transacao_id, versao, vigente, excluida, tipo, perna, parcela, conta_id,
         data_transacao, valor, bruto, imposto, descricao, competencia, pessoa_id)
    SELECT t.user_id, t.transacao_id, p_versao + 1, true, true, t.tipo, t.perna, t.parcela,
           t.conta_id, t.data_transacao, t.valor, t.bruto, t.imposto, t.descricao,
           t.competencia, t.pessoa_id
    FROM transacao_versao t
    WHERE t.user_id = p_user AND t.transacao_id = p_transacao AND t.versao = p_versao;
    RETURN p_versao + 1;
END
$$
"""

# Base: a função de escrita da 0006 com o tipo `repasse` liberado e a pessoa. O guarda do
# estorno (0007) fica na função pública.
SQL_LANCAMENTO_GRAVAR_BASE = """
CREATE FUNCTION lancamento_gravar_base(
    p_user bigint, p_transacao bigint, p_versao integer,
    p_tipo text, p_data date, p_valor numeric,
    p_conta bigint, p_conta_destino bigint,
    p_bruto numeric, p_imposto numeric, p_descricao text,
    p_chave text, p_hash text, p_parcelas integer DEFAULT NULL, p_pessoa bigint DEFAULT NULL
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

    IF p_tipo IS NULL OR p_tipo NOT IN
       ('debito', 'credito', 'receita', 'transferencia', 'investimento', 'repasse',
        'rendimento') THEN
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
    -- Terceiro só existe na compra a crédito (100% da pessoa) e no repasse (ADR 045).
    IF p_pessoa IS NOT NULL AND p_tipo NOT IN ('credito', 'repasse') THEN
        PERFORM abako_erro('AB422', 'pessoa só na compra a crédito ou no repasse');
    END IF;
    IF p_tipo = 'repasse' AND p_pessoa IS NULL THEN
        PERFORM abako_erro('AB422', 'o repasse precisa de uma pessoa');
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
        IF p_tipo = 'repasse' AND v_tipo_conta <> 'corrente' THEN
            PERFORM abako_erro('AB422', 'o repasse entra em conta corrente');
        END IF;
    END IF;

    -- A pessoa não é excluída nem renomeada enquanto este lançamento é gravado (FOR SHARE).
    IF p_pessoa IS NOT NULL THEN
        PERFORM 1 FROM pessoa p
        WHERE p.user_id = p_user AND p.pessoa_id = p_pessoa AND p.vigente AND NOT p.excluida
        FOR SHARE;
        IF NOT FOUND THEN
            PERFORM 1 FROM pessoa p
            WHERE p.user_id = p_user AND p.pessoa_id = p_pessoa AND p.vigente
              AND NOT p.excluida
            FOR SHARE;
            IF NOT FOUND THEN
                PERFORM abako_erro('AB404', 'pessoa não encontrada');
            END IF;
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
             valor, descricao, competencia, chave_idempotencia, hash_corpo, pessoa_id)
        SELECT p_user, v_id, v_versao, 'credito', 1, k, p_conta, p_data,
               -(CASE WHEN k < p_parcelas THEN v_base
                      ELSE v_valor - v_base * (p_parcelas - 1) END),
               v_descricao,
               to_char(to_date(v_comp || '-01', 'YYYY-MM-DD') + make_interval(months => k - 1),
                       'YYYY-MM'),
               CASE WHEN k = 1 AND v_versao = 1 THEN p_chave END,
               CASE WHEN k = 1 AND v_versao = 1 AND p_chave IS NOT NULL THEN p_hash END,
               p_pessoa
        FROM generate_series(1, p_parcelas) AS k;
        RETURN QUERY SELECT v_id, v_versao, true;
        RETURN;
    END IF;

    INSERT INTO transacao_versao
        (user_id, transacao_id, versao, tipo, perna, conta_id, data_transacao, valor,
         bruto, imposto, descricao, chave_idempotencia, hash_corpo, pessoa_id)
    VALUES (p_user, v_id, v_versao, p_tipo, 1, p_conta, p_data,
            CASE WHEN p_tipo IN ('debito', 'transferencia', 'investimento')
                 THEN -v_valor ELSE v_valor END,
            CASE WHEN p_tipo = 'rendimento' THEN p_bruto END,
            CASE WHEN p_tipo = 'rendimento' THEN p_imposto END,
            v_descricao,
            CASE WHEN v_versao = 1 THEN p_chave END,
            CASE WHEN v_versao = 1 AND p_chave IS NOT NULL THEN p_hash END,
            CASE WHEN p_tipo = 'repasse' THEN p_pessoa END);
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

SQL_LANCAMENTO_GRAVAR = """
CREATE FUNCTION lancamento_gravar(
    p_user bigint, p_transacao bigint, p_versao integer,
    p_tipo text, p_data date, p_valor numeric,
    p_conta bigint, p_conta_destino bigint,
    p_bruto numeric, p_imposto numeric, p_descricao text,
    p_chave text, p_hash text, p_parcelas integer DEFAULT NULL, p_pessoa bigint DEFAULT NULL
)
RETURNS TABLE (transacao_id bigint, versao integer, criado boolean)
LANGUAGE plpgsql SECURITY DEFINER SET search_path = public, pg_temp AS $$
DECLARE
    v_alvo bigint;
BEGIN
    -- Cartão que receberá a compra a crédito ou o pagamento: trava (e, na conversão, confere)
    -- tanto na criação quanto na edição (guarda do estorno, ADR 044).
    v_alvo := CASE WHEN p_tipo = 'credito' THEN p_conta
                   WHEN p_tipo = 'transferencia' THEN p_conta_destino END;
    IF p_transacao IS NOT NULL OR v_alvo IS NOT NULL THEN
        PERFORM estorno_guarda(p_user, p_transacao, 'editar', v_alvo);
    END IF;
    RETURN QUERY
        SELECT b.transacao_id, b.versao, b.criado
        FROM lancamento_gravar_base(
            p_user, p_transacao, p_versao, p_tipo, p_data, p_valor, p_conta, p_conta_destino,
            p_bruto, p_imposto, p_descricao, p_chave, p_hash, p_parcelas, p_pessoa) b;
END
$$
"""

SQL_TRANSACAO_VIGENTE = """
CREATE OR REPLACE VIEW transacao_vigente WITH (security_invoker = true) AS
SELECT id, user_id, transacao_id, versao, conta_id, data_transacao, valor, descricao,
       tipo, perna, bruto, imposto, parcela, competencia, estorno_de, estorno_credito,
       pessoa_id
FROM transacao_versao
WHERE vigente AND NOT excluida
"""

SQL_LANCAMENTO_VIGENTE = """
CREATE OR REPLACE VIEW lancamento_vigente WITH (security_invoker = true) AS
SELECT p1.user_id, p1.transacao_id, p1.versao, p1.tipo, p1.data_transacao,
       CASE WHEN p1.tipo = 'credito' THEN c.total ELSE abs(p1.valor) END AS valor,
       p1.conta_id, p2.conta_id AS conta_destino_id,
       p1.bruto, p1.imposto, p1.descricao, p1.criado_em,
       c.parcelas, p1.competencia, p1.estorno_de, p1.estorno_credito, p1.pessoa_id
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

SQL_PARCELA_ATIVA = """
CREATE OR REPLACE VIEW parcela_ativa WITH (security_invoker = true) AS
SELECT t.id, t.user_id, t.transacao_id, t.versao, t.conta_id, t.data_transacao, t.valor,
       t.descricao, t.parcela, t.competencia, t.pessoa_id
FROM transacao_vigente t
WHERE t.tipo = 'credito'
  AND NOT EXISTS (
      SELECT 1 FROM transacao_vigente e
      WHERE e.user_id = t.user_id AND e.tipo = 'estorno' AND e.estorno_de = t.transacao_id
  )
"""

SQL_PARCELA_FATURA = """
CREATE OR REPLACE VIEW parcela_fatura WITH (security_invoker = true) AS
SELECT x.id, x.user_id, x.transacao_id, x.versao, x.conta_id, x.data_transacao, x.valor,
       x.descricao, x.parcela, x.competencia, x.parcelas, x.pessoa_id
FROM (
    SELECT t.id, t.user_id, t.transacao_id, t.versao, t.conta_id, t.data_transacao, t.valor,
           t.descricao, t.parcela, t.competencia,
           count(*) OVER (PARTITION BY t.user_id, t.transacao_id) AS parcelas, t.pessoa_id
    FROM transacao_vigente t
    WHERE t.tipo = 'credito'
) x
WHERE NOT EXISTS (
    SELECT 1 FROM transacao_vigente e
    WHERE e.user_id = x.user_id AND e.tipo = 'estorno' AND e.estorno_de = x.transacao_id
      AND e.competencia <= x.competencia
)
"""

# CHECKs da 0007 (restaurados no downgrade) e da 0008.
CK_SINAL_ANTIGO = (
    "     (tipo = 'debito' AND valor < 0)"
    "  OR (tipo = 'credito' AND valor < 0)"
    "  OR (tipo = 'estorno' AND valor > 0)"
    "  OR (tipo = 'receita' AND valor > 0)"
    "  OR (tipo IN ('transferencia', 'investimento')"
    "      AND ((perna = 1 AND valor < 0) OR (perna = 2 AND valor > 0)))"
    "  OR (tipo = 'rendimento' AND valor > 0)"
    "  OR tipo = 'repasse'"
)
CK_SINAL_NOVO = CK_SINAL_ANTIGO.replace(
    "  OR tipo = 'repasse'", "  OR (tipo = 'repasse' AND valor > 0)"
)


def _anterior(arquivo: str) -> ModuleType:
    """Carrega uma migração anterior só para reaproveitar suas definições no downgrade."""
    caminho = Path(__file__).resolve().parent / arquivo
    spec = importlib.util.spec_from_file_location(f"_abako_{caminho.stem}", caminho)
    assert spec is not None and spec.loader is not None
    modulo = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(modulo)
    return modulo


def upgrade() -> None:
    # ---------- pessoa ----------
    op.execute("CREATE SEQUENCE pessoa_id_seq")
    op.execute(
        """
        CREATE TABLE pessoa (
            id         bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
            user_id    bigint  NOT NULL REFERENCES usuario (user_id),
            pessoa_id  bigint  NOT NULL DEFAULT nextval('pessoa_id_seq'),
            versao     integer NOT NULL DEFAULT 1 CHECK (versao >= 1),
            vigente    boolean NOT NULL DEFAULT true,
            excluida   boolean NOT NULL DEFAULT false,
            nome       text    NOT NULL CHECK (btrim(nome) <> '' AND length(nome) <= 80),
            criado_em  timestamptz NOT NULL DEFAULT now(),
            UNIQUE (user_id, pessoa_id, versao)
        )
        """
    )
    op.execute("CREATE UNIQUE INDEX pessoa_vigente_uq ON pessoa (user_id, pessoa_id) WHERE vigente")
    op.execute(
        "CREATE UNIQUE INDEX pessoa_nome_uq ON pessoa (user_id, lower(nome)) "
        "WHERE vigente AND NOT excluida"
    )

    # ---------- lançamentos: pessoa e sinal do repasse ----------
    op.execute("ALTER TABLE transacao_versao ADD COLUMN pessoa_id bigint")
    op.execute(
        "ALTER TABLE transacao_versao ADD CONSTRAINT transacao_versao_pessoa_ck CHECK ("
        "  CASE WHEN tipo = 'repasse' THEN pessoa_id IS NOT NULL"
        "       WHEN tipo = 'credito' THEN true"
        "       ELSE pessoa_id IS NULL END)"
    )
    op.execute("ALTER TABLE transacao_versao DROP CONSTRAINT transacao_versao_sinal_ck")
    op.execute(
        f"ALTER TABLE transacao_versao ADD CONSTRAINT transacao_versao_sinal_ck CHECK ("
        f"{CK_SINAL_NOVO})"
    )
    op.execute(
        "CREATE INDEX transacao_versao_pessoa_idx ON transacao_versao (user_id, pessoa_id) "
        "WHERE vigente AND NOT excluida AND pessoa_id IS NOT NULL"
    )

    op.execute(SQL_TRANSACAO_VIGENTE)
    op.execute(SQL_LANCAMENTO_VIGENTE)
    op.execute(SQL_PARCELA_ATIVA)
    op.execute(SQL_PARCELA_FATURA)

    # ---------- funções ----------
    op.execute(SQL_PERNAS_CK)
    op.execute(SQL_PESSOA_GRAVAR)
    op.execute(SQL_PESSOA_EXCLUIR)
    op.execute(SQL_A_RECEBER)
    op.execute(f"DROP FUNCTION {ASSIN_FATURA_ITENS}")
    op.execute(SQL_FATURA_ITENS)
    op.execute(SQL_FATURA_RESUMO)
    op.execute(SQL_LANCAMENTO_EXCLUIR_BASE)
    # A assinatura de 14 argumentos sai; a de 15 (último com DEFAULT) atende quem chamava com 14.
    op.execute(f"DROP FUNCTION {ASSIN_LANC_ANTIGA}")
    op.execute(f"DROP FUNCTION {ASSIN_LANC_BASE_ANTIGA}")
    op.execute(SQL_LANCAMENTO_GRAVAR_BASE)
    op.execute(SQL_LANCAMENTO_GRAVAR)

    # ---------- papéis ----------
    op.execute("GRANT SELECT ON pessoa TO abako_app")
    # O pipeline lê tudo menos o nome: dado pessoal de terceiro não chega ao analítico (ADR 045).
    op.execute(
        "GRANT SELECT (id, user_id, pessoa_id, versao, vigente, excluida, criado_em) "
        "ON pessoa TO abako_pipeline"
    )
    op.execute(f"REVOKE ALL ON FUNCTION {ASSIN_LANC_BASE} FROM PUBLIC, abako_app")
    for assinatura in (*FUNCOES_NOVAS, ASSIN_FATURA_ITENS, ASSIN_LANC):
        op.execute(f"REVOKE ALL ON FUNCTION {assinatura} FROM PUBLIC")
    for assinatura in FUNCOES_APP:
        op.execute(f"GRANT EXECUTE ON FUNCTION {assinatura} TO abako_app")


def downgrade() -> None:
    # Irreversível com dados (ADR 045): voltar apagaria pessoas, repasses e o vínculo das compras.
    op.execute(
        """
        DO $$
        BEGIN
            IF EXISTS (SELECT 1 FROM pessoa)
               OR EXISTS (SELECT 1 FROM transacao_versao
                          WHERE pessoa_id IS NOT NULL OR tipo = 'repasse') THEN
                RAISE EXCEPTION USING MESSAGE =
                    '0008: há pessoa, repasse ou compra de terceiro que só existem nesta '
                    'versão; o downgrade apagaria dados. Restaure o backup anterior à 0008 '
                    '(ADR 045).';
            END IF;
        END $$
        """
    )
    m6 = _anterior("0006_cartao_fatura.py")
    m7 = _anterior("0007_estorno.py")

    # funções: de volta às definições da 0006 (escrita) e da 0007 (guarda, fatura)
    op.execute(f"DROP FUNCTION {ASSIN_LANC}")
    op.execute(f"DROP FUNCTION {ASSIN_LANC_BASE}")
    op.execute(
        m6.SQL_LANCAMENTO_GRAVAR.replace(
            "CREATE FUNCTION lancamento_gravar(", "CREATE FUNCTION lancamento_gravar_base(", 1
        )
    )
    op.execute(
        m6.SQL_LANCAMENTO_EXCLUIR.replace(
            "FUNCTION lancamento_excluir(", "FUNCTION lancamento_excluir_base(", 1
        )
    )
    op.execute(m7.SQL_LANCAMENTO_GRAVAR)
    op.execute(f"REVOKE ALL ON FUNCTION {ASSIN_LANC_BASE_ANTIGA} FROM PUBLIC, abako_app")
    op.execute(f"REVOKE ALL ON FUNCTION {ASSIN_LANC_ANTIGA} FROM PUBLIC")
    op.execute(f"GRANT EXECUTE ON FUNCTION {ASSIN_LANC_ANTIGA} TO abako_app")

    op.execute(f"DROP FUNCTION {ASSIN_FATURA_ITENS}")
    op.execute(m7.SQL_FATURA_ITENS)
    op.execute(f"REVOKE ALL ON FUNCTION {ASSIN_FATURA_ITENS} FROM PUBLIC")
    op.execute(f"GRANT EXECUTE ON FUNCTION {ASSIN_FATURA_ITENS} TO abako_app")
    op.execute(m6.SQL_PERNAS_CK)
    for assinatura in FUNCOES_NOVAS:
        op.execute(f"DROP FUNCTION {assinatura}")

    # views: sem a coluna pessoa_id (recriadas como na 0007)
    op.execute("DROP VIEW parcela_fatura")
    op.execute("DROP VIEW parcela_ativa")
    op.execute("DROP VIEW lancamento_vigente")
    op.execute("DROP VIEW transacao_vigente")
    op.execute(m7.SQL_TRANSACAO_VIGENTE)
    op.execute(m7.SQL_LANCAMENTO_VIGENTE)
    op.execute(m7.SQL_PARCELA_ATIVA)
    op.execute(m7.SQL_PARCELA_FATURA)
    op.execute(
        "GRANT SELECT ON transacao_vigente, lancamento_vigente, parcela_ativa, parcela_fatura "
        "TO abako_app, abako_pipeline"
    )

    # tabela
    op.execute("DROP INDEX transacao_versao_pessoa_idx")
    op.execute("ALTER TABLE transacao_versao DROP CONSTRAINT transacao_versao_sinal_ck")
    op.execute(
        f"ALTER TABLE transacao_versao ADD CONSTRAINT transacao_versao_sinal_ck CHECK ("
        f"{CK_SINAL_ANTIGO})"
    )
    op.execute("ALTER TABLE transacao_versao DROP CONSTRAINT transacao_versao_pessoa_ck")
    op.execute("ALTER TABLE transacao_versao DROP COLUMN pessoa_id")
    op.execute("DROP TABLE pessoa")
    op.execute("DROP SEQUENCE pessoa_id_seq")
