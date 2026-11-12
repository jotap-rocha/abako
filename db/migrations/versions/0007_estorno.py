"""estorno da compra a crédito e alocação do pago às parcelas (SPEC-006, ADR 044)

Revision ID: 0007
Revises: 0006

SQL puro (ADR 025). A regra vive no banco (ADR 015):

- Tipo `estorno`: UMA linha positiva (+T) na conta de dívida, ligada à compra por `estorno_de`
  (o `transacao_id` da compra, preservada e imutável). `estorno_credito` guarda o P emitido
  (parte paga, que vira crédito); N = T - P é o limite devolvido. No máximo um estorno vigente
  por compra, sempre da compra inteira. Sem perna na conta corrente: movimento = 0.
- `competencia` do estorno = a "próxima fatura aberta": competência que uma compra teria na data
  do estorno (regra do dia do fechamento e fechamento vigente, ADR 043 itens 1 e 5).
- Leitura do pago (ADR 044 item 1), recomputada a cada consulta, nunca gravada:
  `pool_pago` = pagamentos recebidos pelo cartão - créditos de estorno já emitidos;
  `alocacao_pago` aloca o pool às parcelas ativas por competência, data da compra, nº da
  parcela (e `transacao_id` só para desempate); `compra_paga` devolve T, P e N de uma compra.
- `parcela_ativa`: parcelas vigentes de compras NÃO estornadas; fonte da alocação do pago e do
  gasto real (que sai das competências originais, ADR 044 item 5).
- `parcela_fatura`: parcelas que as faturas mostram. A compra estornada some só das competências
  IGUAIS OU POSTERIORES à do crédito; faturas anteriores mantêm o valor (ADR 044 item 10).
  `fatura_itens`/`fatura_total` usam essa view e descontam o crédito P na competência do estorno.
- Escrita só por funções SECURITY DEFINER (`estorno_gravar`); `abako_app` não escreve nas tabelas.
- Recusas (ADR 044 itens 8 e 9), sob trava por (usuário, cartão) para o pool não ficar negativo
  em corrida: editar ou excluir compra com P > 0; depois de um estorno no cartão, editar ou
  excluir QUALQUER lançamento já gravado nele (lançamento novo segue permitido). Para não
  reescrever as funções de escrita da 0006, elas são renomeadas para `*_base` (sem acesso ao
  app) e as funções públicas de mesmo nome e assinatura chamam o guarda e depois a base.
"""

from alembic import op

revision = "0007"
down_revision = "0006"
branch_labels = None
depends_on = None

TIPOS_LANCAMENTO = (
    "'debito', 'credito', 'receita', 'transferencia', 'investimento', 'repasse', 'rendimento'"
)
TIPOS_LANCAMENTO_NOVOS = TIPOS_LANCAMENTO + ", 'estorno'"

ASSIN_LANC = (
    "lancamento_gravar(bigint, bigint, integer, text, date, numeric, bigint, bigint, "
    "numeric, numeric, text, text, text, integer)"
)
ASSIN_LANC_BASE = ASSIN_LANC.replace("lancamento_gravar(", "lancamento_gravar_base(")
ASSIN_EXCL = "lancamento_excluir(bigint, bigint, integer)"
ASSIN_EXCL_BASE = ASSIN_EXCL.replace("lancamento_excluir(", "lancamento_excluir_base(")

FUNCOES_APP = (
    "estorno_gravar(bigint, bigint, integer, date, text)",
    "pool_pago(bigint, bigint)",
    "alocacao_pago(bigint, bigint)",
    "compra_paga(bigint, bigint)",
)
FUNCOES_INTERNAS = (
    "cartao_trava(bigint, bigint)",
    "estorno_guarda(bigint, bigint, text, bigint)",
)

# ---------------------------------------------------------------------------------------------
# Funções novas
# ---------------------------------------------------------------------------------------------

SQL_PARCELA_ATIVA = """
CREATE VIEW parcela_ativa WITH (security_invoker = true) AS
SELECT t.id, t.user_id, t.transacao_id, t.versao, t.conta_id, t.data_transacao, t.valor,
       t.descricao, t.parcela, t.competencia
FROM transacao_vigente t
WHERE t.tipo = 'credito'
  AND NOT EXISTS (
      SELECT 1 FROM transacao_vigente e
      WHERE e.user_id = t.user_id AND e.tipo = 'estorno' AND e.estorno_de = t.transacao_id
  )
"""

SQL_POOL_PAGO = """
CREATE FUNCTION pool_pago(p_user bigint, p_conta bigint)
RETURNS numeric
LANGUAGE sql STABLE AS $$
    SELECT COALESCE((SELECT sum(t.valor) FROM transacao_vigente t
                     WHERE t.user_id = p_user AND t.conta_id = p_conta
                       AND t.tipo = 'transferencia' AND t.perna = 2), 0)
         - COALESCE((SELECT sum(e.estorno_credito) FROM transacao_vigente e
                     WHERE e.user_id = p_user AND e.conta_id = p_conta
                       AND e.tipo = 'estorno'), 0)
$$
"""

SQL_ALOCACAO_PAGO = """
CREATE FUNCTION alocacao_pago(p_user bigint, p_conta bigint)
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
           greatest(0, least(o.valor, pool_pago(p_user, p_conta) - o.antes))
    FROM o
    ORDER BY o.competencia, o.data_transacao, o.parcela, o.transacao_id
$$
"""

SQL_COMPRA_PAGA = """
CREATE FUNCTION compra_paga(p_user bigint, p_transacao bigint)
RETURNS TABLE (total numeric, pago numeric, nao_pago numeric)
LANGUAGE sql STABLE AS $$
    WITH c AS (
        SELECT t.conta_id, -sum(t.valor) AS total
        FROM transacao_vigente t
        WHERE t.user_id = p_user AND t.transacao_id = p_transacao AND t.tipo = 'credito'
        GROUP BY t.conta_id
    )
    SELECT c.total,
           COALESCE(sum(a.alocado), 0),
           c.total - COALESCE(sum(a.alocado), 0)
    FROM c
    LEFT JOIN LATERAL alocacao_pago(p_user, c.conta_id) a ON a.transacao_id = p_transacao
    GROUP BY c.total
$$
"""

SQL_CARTAO_TRAVA = """
CREATE FUNCTION cartao_trava(p_user bigint, p_conta bigint)
RETURNS void
LANGUAGE sql AS $$
    SELECT pg_advisory_xact_lock(
        hashtextextended('cartao:' || p_user::text || ':' || p_conta::text, 0))
$$
"""

SQL_ESTORNO_GUARDA = """
CREATE FUNCTION estorno_guarda(
    p_user bigint, p_transacao bigint, p_acao text, p_alvo bigint DEFAULT NULL
)
RETURNS void
LANGUAGE plpgsql SECURITY DEFINER SET search_path = public, pg_temp AS $$
DECLARE
    v_tipo text;
    v_cartao bigint;
    v_alvo bigint;
    v_pago numeric;
BEGIN
    -- Lançamento existente (edição/exclusão): a linha no cartão, se houver, vem primeiro
    -- (pagamento tem a perna 2 nele). Sem p_transacao é criação: só o cartão de destino conta.
    IF p_transacao IS NOT NULL THEN
        SELECT t.tipo, c.conta_id INTO v_tipo, v_cartao
        FROM transacao_versao t
        LEFT JOIN conta_versao c
               ON c.user_id = t.user_id AND c.conta_id = t.conta_id
              AND c.vigente AND NOT c.excluida AND c.tipo = 'divida'
        WHERE t.user_id = p_user AND t.transacao_id = p_transacao AND t.vigente
          AND NOT t.excluida
        ORDER BY (c.conta_id IS NULL), t.perna, t.parcela
        LIMIT 1;
        -- sem linha vigente a função de escrita responde 404/409
    END IF;
    IF v_tipo = 'estorno' THEN
        PERFORM abako_erro('AB422',
            'o estorno não pode ser editado nem excluído (ADR 044)');
    END IF;

    -- Cartão para o qual o lançamento aponta depois da gravação (compra a crédito ou
    -- pagamento); só vale se a conta for mesmo um cartão.
    IF p_alvo IS NOT NULL THEN
        SELECT c.conta_id INTO v_alvo FROM conta_versao c
        WHERE c.user_id = p_user AND c.conta_id = p_alvo AND c.vigente AND NOT c.excluida
          AND c.tipo = 'divida';
    END IF;

    -- Travas por cartão sempre em ordem crescente de conta: duas gravações que tocam os
    -- mesmos cartões em ordens opostas não ficam em deadlock.
    IF v_cartao IS NOT NULL AND v_alvo IS NOT NULL AND v_cartao <> v_alvo THEN
        PERFORM cartao_trava(p_user, least(v_cartao, v_alvo));
        PERFORM cartao_trava(p_user, greatest(v_cartao, v_alvo));
    ELSIF coalesce(v_cartao, v_alvo) IS NOT NULL THEN
        PERFORM cartao_trava(p_user, coalesce(v_cartao, v_alvo));
    END IF;

    IF v_cartao IS NOT NULL THEN
        IF EXISTS (SELECT 1 FROM transacao_vigente e
                   WHERE e.user_id = p_user AND e.conta_id = v_cartao
                     AND e.tipo = 'estorno') THEN
            IF v_tipo = 'transferencia' THEN
                PERFORM abako_erro('AB422',
                    'este cartão tem estorno: o pagamento recebido por ele não pode ser '
                    'editado nem excluído (ADR 044)');
            END IF;
            IF v_tipo = 'credito' AND EXISTS (
                SELECT 1 FROM transacao_vigente e
                WHERE e.user_id = p_user AND e.tipo = 'estorno' AND e.estorno_de = p_transacao
            ) THEN
                PERFORM abako_erro('AB422',
                    'a compra foi estornada e não pode ser editada nem excluída (ADR 044)');
            END IF;
            PERFORM abako_erro('AB422',
                'este cartão tem estorno: os lançamentos já gravados nele não podem ser '
                'editados nem excluídos; só lançamentos novos (ADR 044)');
        END IF;

        IF v_tipo = 'credito' THEN
            SELECT c.pago INTO v_pago FROM compra_paga(p_user, p_transacao) c;
            IF COALESCE(v_pago, 0) > 0 THEN
                IF p_acao = 'excluir' THEN
                    PERFORM abako_erro('AB422',
                        'a compra tem parte paga e não pode ser excluída: estorne a compra '
                        'e lance de novo (ADR 044)');
                END IF;
                PERFORM abako_erro('AB422',
                    'a compra tem parte paga e não pode ser editada: estorne a compra e '
                    'lance de novo (ADR 044)');
            END IF;
        END IF;
    END IF;

    -- Conversão: um lançamento já gravado não passa a ser compra/pagamento de um cartão que
    -- já tem estorno (isso mudaria a alocação do pago); só lançamento novo entra.
    IF p_transacao IS NOT NULL AND v_alvo IS NOT NULL AND v_alvo IS DISTINCT FROM v_cartao
       AND EXISTS (SELECT 1 FROM transacao_vigente e
                   WHERE e.user_id = p_user AND e.conta_id = v_alvo AND e.tipo = 'estorno') THEN
        PERFORM abako_erro('AB422',
            'o cartão de destino tem estorno: um lançamento já gravado não pode virar compra '
            'ou pagamento dele; só lançamentos novos (ADR 044)');
    END IF;
END
$$
"""

SQL_ESTORNO_GRAVAR = """
CREATE FUNCTION estorno_gravar(
    p_user bigint, p_transacao bigint, p_versao integer, p_data date, p_descricao text
)
RETURNS TABLE (
    estorno_id bigint, competencia_credito text, total numeric, credito numeric,
    limite_devolvido numeric
)
LANGUAGE plpgsql SECURITY DEFINER SET search_path = public, pg_temp AS $$
DECLARE
    v_hoje date := (now() AT TIME ZONE 'America/Sao_Paulo')::date;
    v_descricao text := nullif(btrim(p_descricao), '');
    v_conta bigint;
    v_tipo text;
    v_versao_atual integer;
    v_data_compra date;
    v_total numeric;
    v_pago numeric;
    v_comp text;
    v_id bigint;
BEGIN
    IF p_data IS NULL OR p_data < DATE '2000-01-01' OR p_data > v_hoje THEN
        PERFORM abako_erro('AB422', 'a data precisa estar entre 2000 e hoje');
    END IF;
    IF v_descricao IS NOT NULL AND length(v_descricao) > 200 THEN
        PERFORM abako_erro('AB422', 'a descrição passa de 200 caracteres');
    END IF;

    SELECT t.conta_id INTO v_conta FROM transacao_versao t
    WHERE t.user_id = p_user AND t.transacao_id = p_transacao AND t.vigente
      AND NOT t.excluida AND t.perna = 1 AND t.parcela = 1;
    IF NOT FOUND THEN
        PERFORM abako_erro('AB404', 'lançamento não encontrado');
    END IF;

    -- Mesma trava das edições do cartão: o pool de pagamentos não muda durante o estorno.
    PERFORM cartao_trava(p_user, v_conta);

    SELECT t.tipo, t.versao, t.data_transacao INTO v_tipo, v_versao_atual, v_data_compra
    FROM transacao_versao t
    WHERE t.user_id = p_user AND t.transacao_id = p_transacao AND t.vigente
      AND NOT t.excluida AND t.perna = 1 AND t.parcela = 1
    FOR UPDATE;
    IF NOT FOUND THEN
        PERFORM abako_erro('AB409', 'o lançamento mudou desde a última leitura');
    END IF;
    IF v_tipo <> 'credito' THEN
        PERFORM abako_erro('AB422', 'só a compra a crédito pode ser estornada');
    END IF;
    IF v_versao_atual IS DISTINCT FROM p_versao THEN
        PERFORM abako_erro('AB409', 'o lançamento mudou desde a última leitura');
    END IF;
    IF p_data < v_data_compra THEN
        PERFORM abako_erro('AB422', 'o estorno não pode ser anterior à compra');
    END IF;
    IF EXISTS (SELECT 1 FROM transacao_vigente e
               WHERE e.user_id = p_user AND e.tipo = 'estorno' AND e.estorno_de = p_transacao) THEN
        PERFORM abako_erro('AB410', 'a compra já foi estornada');
    END IF;

    v_comp := competencia_compra(p_user, v_conta, p_data);
    IF v_comp IS NULL THEN
        PERFORM abako_erro('AB422', 'o cartão não tem fechamento vigente nessa data');
    END IF;

    SELECT c.total, c.pago INTO v_total, v_pago FROM compra_paga(p_user, p_transacao) c;

    v_id := nextval('transacao_id_seq');
    BEGIN
        INSERT INTO transacao_versao
            (user_id, transacao_id, versao, tipo, perna, parcela, conta_id, data_transacao,
             valor, descricao, competencia, estorno_de, estorno_credito)
        VALUES (p_user, v_id, 1, 'estorno', 1, 1, v_conta, p_data, v_total, v_descricao,
                v_comp, p_transacao, v_pago);
    EXCEPTION WHEN unique_violation THEN
        PERFORM abako_erro('AB410', 'a compra já foi estornada');
    END;
    RETURN QUERY SELECT v_id, v_comp, v_total, v_pago, v_total - v_pago;
END
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
    v_alvo bigint;
BEGIN
    -- Cartão que receberá a compra a crédito ou o pagamento: trava (e, na conversão, confere)
    -- tanto na criação quanto na edição.
    v_alvo := CASE WHEN p_tipo = 'credito' THEN p_conta
                   WHEN p_tipo = 'transferencia' THEN p_conta_destino END;
    IF p_transacao IS NOT NULL OR v_alvo IS NOT NULL THEN
        PERFORM estorno_guarda(p_user, p_transacao, 'editar', v_alvo);
    END IF;
    RETURN QUERY
        SELECT b.transacao_id, b.versao, b.criado
        FROM lancamento_gravar_base(
            p_user, p_transacao, p_versao, p_tipo, p_data, p_valor, p_conta, p_conta_destino,
            p_bruto, p_imposto, p_descricao, p_chave, p_hash, p_parcelas) b;
END
$$
"""

SQL_LANCAMENTO_EXCLUIR = """
CREATE FUNCTION lancamento_excluir(p_user bigint, p_transacao bigint, p_versao integer)
RETURNS integer
LANGUAGE plpgsql SECURITY DEFINER SET search_path = public, pg_temp AS $$
BEGIN
    PERFORM estorno_guarda(p_user, p_transacao, 'excluir');
    RETURN lancamento_excluir_base(p_user, p_transacao, p_versao);
END
$$
"""

# O que a fatura mostra: a compra estornada some só a partir da competência do crédito.
SQL_PARCELA_FATURA = """
CREATE VIEW parcela_fatura WITH (security_invoker = true) AS
SELECT x.id, x.user_id, x.transacao_id, x.versao, x.conta_id, x.data_transacao, x.valor,
       x.descricao, x.parcela, x.competencia, x.parcelas
FROM (
    SELECT t.id, t.user_id, t.transacao_id, t.versao, t.conta_id, t.data_transacao, t.valor,
           t.descricao, t.parcela, t.competencia,
           count(*) OVER (PARTITION BY t.user_id, t.transacao_id) AS parcelas
    FROM transacao_vigente t
    WHERE t.tipo = 'credito'
) x
WHERE NOT EXISTS (
    SELECT 1 FROM transacao_vigente e
    WHERE e.user_id = x.user_id AND e.tipo = 'estorno' AND e.estorno_de = x.transacao_id
      AND e.competencia <= x.competencia
)
"""

# Fatura: parcelas da competência (ver acima), menos o crédito P dos estornos nela.
SQL_FATURA_ITENS = """
CREATE OR REPLACE FUNCTION fatura_itens(p_user bigint, p_conta bigint, p_competencia text)
RETURNS TABLE (
    transacao_id bigint, versao integer, parcela integer, parcelas integer,
    data_compra date, valor numeric, descricao text
)
LANGUAGE sql STABLE AS $$
    SELECT u.transacao_id, u.versao, u.parcela, u.parcelas, u.data_compra, u.valor, u.descricao
    FROM (
        SELECT x.transacao_id, x.versao, x.parcela::int AS parcela, x.n::int AS parcelas,
               x.data_transacao AS data_compra, -x.valor AS valor, x.descricao
        FROM (
            SELECT t.transacao_id, t.versao, t.parcela, t.data_transacao, t.valor, t.descricao,
                   t.competencia, t.parcelas AS n
            FROM parcela_fatura t
            WHERE t.user_id = p_user AND t.conta_id = p_conta
        ) x
        WHERE x.competencia = p_competencia
        UNION ALL
        SELECT e.transacao_id, e.versao, 1, 1, e.data_transacao, -e.estorno_credito, e.descricao
        FROM transacao_vigente e
        WHERE e.user_id = p_user AND e.conta_id = p_conta AND e.tipo = 'estorno'
          AND e.competencia = p_competencia AND e.estorno_credito > 0
    ) u
    ORDER BY u.data_compra, u.transacao_id, u.parcela
$$
"""

SQL_FATURA_TOTAL = """
CREATE OR REPLACE FUNCTION fatura_total(p_user bigint, p_conta bigint, p_competencia text)
RETURNS numeric
LANGUAGE sql STABLE AS $$
    SELECT COALESCE((SELECT sum(-t.valor) FROM parcela_fatura t
                     WHERE t.user_id = p_user AND t.conta_id = p_conta
                       AND t.competencia = p_competencia), 0)
         - COALESCE((SELECT sum(e.estorno_credito) FROM transacao_vigente e
                     WHERE e.user_id = p_user AND e.conta_id = p_conta
                       AND e.tipo = 'estorno' AND e.competencia = p_competencia), 0)
$$
"""

SQL_TRANSACAO_VIGENTE = """
CREATE OR REPLACE VIEW transacao_vigente WITH (security_invoker = true) AS
SELECT id, user_id, transacao_id, versao, conta_id, data_transacao, valor, descricao,
       tipo, perna, bruto, imposto, parcela, competencia, estorno_de, estorno_credito
FROM transacao_versao
WHERE vigente AND NOT excluida
"""

SQL_LANCAMENTO_VIGENTE = """
CREATE OR REPLACE VIEW lancamento_vigente WITH (security_invoker = true) AS
SELECT p1.user_id, p1.transacao_id, p1.versao, p1.tipo, p1.data_transacao,
       CASE WHEN p1.tipo = 'credito' THEN c.total ELSE abs(p1.valor) END AS valor,
       p1.conta_id, p2.conta_id AS conta_destino_id,
       p1.bruto, p1.imposto, p1.descricao, p1.criado_em,
       c.parcelas, p1.competencia, p1.estorno_de, p1.estorno_credito
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

# ---------------------------------------------------------------------------------------------
# Definições da 0006 (restauradas no downgrade)
# ---------------------------------------------------------------------------------------------

ANTIGA_FATURA_ITENS = """
CREATE OR REPLACE FUNCTION fatura_itens(p_user bigint, p_conta bigint, p_competencia text)
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

ANTIGA_FATURA_TOTAL = """
CREATE OR REPLACE FUNCTION fatura_total(p_user bigint, p_conta bigint, p_competencia text)
RETURNS numeric
LANGUAGE sql STABLE AS $$
    SELECT COALESCE(sum(-t.valor), 0)
    FROM transacao_vigente t
    WHERE t.user_id = p_user AND t.conta_id = p_conta AND t.tipo = 'credito'
      AND t.competencia = p_competencia
$$
"""

ANTIGA_TRANSACAO_VIGENTE = """
CREATE VIEW transacao_vigente WITH (security_invoker = true) AS
SELECT id, user_id, transacao_id, versao, conta_id, data_transacao, valor, descricao,
       tipo, perna, bruto, imposto, parcela, competencia
FROM transacao_versao
WHERE vigente AND NOT excluida
"""

ANTIGA_LANCAMENTO_VIGENTE = """
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


def upgrade() -> None:
    # ---------- tabela: tipo, vínculo e crédito ----------
    op.execute("ALTER TABLE transacao_versao ADD COLUMN estorno_de bigint")
    op.execute("ALTER TABLE transacao_versao ADD COLUMN estorno_credito numeric(14, 2)")
    op.execute("ALTER TABLE transacao_versao DROP CONSTRAINT transacao_versao_tipo_ck")
    op.execute(
        f"ALTER TABLE transacao_versao ADD CONSTRAINT transacao_versao_tipo_ck "
        f"CHECK (tipo IN ({TIPOS_LANCAMENTO_NOVOS}))"
    )
    op.execute("ALTER TABLE transacao_versao DROP CONSTRAINT transacao_versao_sinal_ck")
    op.execute(
        "ALTER TABLE transacao_versao ADD CONSTRAINT transacao_versao_sinal_ck CHECK ("
        "     (tipo = 'debito' AND valor < 0)"
        "  OR (tipo = 'credito' AND valor < 0)"
        "  OR (tipo = 'estorno' AND valor > 0)"  # +T na conta de dívida (ADR 044)
        "  OR (tipo = 'receita' AND valor > 0)"
        "  OR (tipo IN ('transferencia', 'investimento')"
        "      AND ((perna = 1 AND valor < 0) OR (perna = 2 AND valor > 0)))"
        "  OR (tipo = 'rendimento' AND valor > 0)"
        "  OR tipo = 'repasse')"
    )
    op.execute("ALTER TABLE transacao_versao DROP CONSTRAINT transacao_versao_competencia_ck")
    op.execute(
        "ALTER TABLE transacao_versao ADD CONSTRAINT transacao_versao_competencia_ck CHECK ("
        "  CASE WHEN tipo IN ('credito', 'estorno')"
        "       THEN coalesce(competencia ~ '^[0-9]{4}-(0[1-9]|1[0-2])$', false)"
        "       ELSE competencia IS NULL END)"
    )
    op.execute(
        "ALTER TABLE transacao_versao ADD CONSTRAINT transacao_versao_estorno_ck CHECK ("
        "  ((tipo = 'estorno') = (estorno_de IS NOT NULL))"
        "  AND ((tipo = 'estorno') = (estorno_credito IS NOT NULL))"
        "  AND (tipo <> 'estorno' OR (estorno_credito >= 0 AND estorno_credito <= valor"
        "                              AND perna = 1 AND parcela = 1)))"
    )
    # No máximo um estorno vigente por compra.
    op.execute(
        "CREATE UNIQUE INDEX transacao_versao_estorno_uq ON transacao_versao "
        "(user_id, estorno_de) WHERE tipo = 'estorno' AND vigente AND NOT excluida"
    )
    # Pagamentos recebidos pelo cartão (pool) e estornos do cartão.
    op.execute(
        "CREATE INDEX transacao_versao_cartao_idx ON transacao_versao (user_id, conta_id, tipo) "
        "WHERE vigente AND NOT excluida AND tipo IN ('transferencia', 'estorno')"
    )

    op.execute(SQL_TRANSACAO_VIGENTE)
    op.execute(SQL_LANCAMENTO_VIGENTE)
    op.execute(SQL_PARCELA_ATIVA)
    op.execute(SQL_PARCELA_FATURA)

    # ---------- funções ----------
    op.execute(SQL_POOL_PAGO)
    op.execute(SQL_ALOCACAO_PAGO)
    op.execute(SQL_COMPRA_PAGA)
    op.execute(SQL_CARTAO_TRAVA)
    op.execute(SQL_ESTORNO_GUARDA)
    op.execute(SQL_ESTORNO_GRAVAR)
    op.execute(SQL_FATURA_ITENS)
    op.execute(SQL_FATURA_TOTAL)

    # As funções de escrita da 0006 viram a base; as públicas chamam o guarda antes.
    op.execute(f"ALTER FUNCTION {ASSIN_LANC} RENAME TO lancamento_gravar_base")
    op.execute(f"ALTER FUNCTION {ASSIN_EXCL} RENAME TO lancamento_excluir_base")
    op.execute(SQL_LANCAMENTO_GRAVAR)
    op.execute(SQL_LANCAMENTO_EXCLUIR)

    # ---------- papéis ----------
    op.execute("GRANT SELECT ON parcela_ativa, parcela_fatura TO abako_app, abako_pipeline")
    op.execute("GRANT SELECT ON transacao_vigente, lancamento_vigente TO abako_app, abako_pipeline")
    for assinatura in (ASSIN_LANC_BASE, ASSIN_EXCL_BASE, *FUNCOES_INTERNAS):
        op.execute(f"REVOKE ALL ON FUNCTION {assinatura} FROM PUBLIC, abako_app")
    for assinatura in (ASSIN_LANC, ASSIN_EXCL, *FUNCOES_APP):
        op.execute(f"REVOKE ALL ON FUNCTION {assinatura} FROM PUBLIC")
        op.execute(f"GRANT EXECUTE ON FUNCTION {assinatura} TO abako_app")


def downgrade() -> None:
    # Irreversível com dados (ADR 044): voltar apagaria o estorno e o crédito dele.
    op.execute(
        """
        DO $$
        BEGIN
            IF EXISTS (SELECT 1 FROM transacao_versao WHERE tipo = 'estorno') THEN
                RAISE EXCEPTION USING MESSAGE =
                    '0007: há estorno que só existe nesta versão; o downgrade apagaria dados. '
                    'Restaure o backup anterior à 0007 (ADR 044).';
            END IF;
        END $$
        """
    )
    op.execute(f"DROP FUNCTION {ASSIN_LANC}")
    op.execute(f"DROP FUNCTION {ASSIN_EXCL}")
    op.execute(f"ALTER FUNCTION {ASSIN_LANC_BASE} RENAME TO lancamento_gravar")
    op.execute(f"ALTER FUNCTION {ASSIN_EXCL_BASE} RENAME TO lancamento_excluir")
    for assinatura in (ASSIN_LANC, ASSIN_EXCL):
        op.execute(f"REVOKE ALL ON FUNCTION {assinatura} FROM PUBLIC")
        op.execute(f"GRANT EXECUTE ON FUNCTION {assinatura} TO abako_app")

    op.execute(ANTIGA_FATURA_ITENS)
    op.execute(ANTIGA_FATURA_TOTAL)
    for assinatura in (
        "estorno_gravar(bigint, bigint, integer, date, text)",
        "estorno_guarda(bigint, bigint, text, bigint)",
        "cartao_trava(bigint, bigint)",
        "compra_paga(bigint, bigint)",
        "alocacao_pago(bigint, bigint)",
        "pool_pago(bigint, bigint)",
    ):
        op.execute(f"DROP FUNCTION {assinatura}")

    op.execute("DROP VIEW parcela_fatura")
    op.execute("DROP VIEW parcela_ativa")
    op.execute("DROP VIEW lancamento_vigente")
    op.execute("DROP VIEW transacao_vigente")
    op.execute(ANTIGA_TRANSACAO_VIGENTE)
    op.execute(ANTIGA_LANCAMENTO_VIGENTE)
    op.execute("GRANT SELECT ON lancamento_vigente, transacao_vigente TO abako_app, abako_pipeline")

    op.execute("DROP INDEX transacao_versao_cartao_idx")
    op.execute("DROP INDEX transacao_versao_estorno_uq")
    op.execute("ALTER TABLE transacao_versao DROP CONSTRAINT transacao_versao_estorno_ck")
    op.execute("ALTER TABLE transacao_versao DROP CONSTRAINT transacao_versao_competencia_ck")
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
        "  OR (tipo = 'credito' AND valor < 0)"
        "  OR (tipo = 'receita' AND valor > 0)"
        "  OR (tipo IN ('transferencia', 'investimento')"
        "      AND ((perna = 1 AND valor < 0) OR (perna = 2 AND valor > 0)))"
        "  OR (tipo = 'rendimento' AND valor > 0)"
        "  OR tipo = 'repasse')"
    )
    op.execute("ALTER TABLE transacao_versao DROP CONSTRAINT transacao_versao_tipo_ck")
    op.execute(
        f"ALTER TABLE transacao_versao ADD CONSTRAINT transacao_versao_tipo_ck "
        f"CHECK (tipo IN ({TIPOS_LANCAMENTO}))"
    )
    op.execute("ALTER TABLE transacao_versao DROP COLUMN estorno_credito")
    op.execute("ALTER TABLE transacao_versao DROP COLUMN estorno_de")
