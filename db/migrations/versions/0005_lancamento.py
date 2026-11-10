"""lançamento por tipo, tipos de conta e escrita versionada por função (SPEC-004, ADR 042)

Revision ID: 0005
Revises: 0004

SQL puro (ADR 025). A regra de lançamento vive aqui, no banco (ADR 015):

- `conta_versao.tipo` (corrente | reserva | investimento | beneficio) e `conta_mae_id` (a
  caixinha/cofre pertence a uma conta corrente do mesmo banco, com saldo próprio).
- `transacao_versao.tipo/perna/bruto/imposto/hash_corpo`. Transferência e investimento são um
  `transacao_id` com duas pernas (mesma versão), soma zero (INV-01).
- O valor chega positivo; o sinal vem do tipo (débito −, receita +, perna 1 −, perna 2 +,
  rendimento + com valor = bruto − imposto).
- Escrita só pelas funções `conta_gravar`, `lancamento_gravar` e `lancamento_excluir`
  (SECURITY DEFINER): validam, fecham a versão vigente e gravam a nova na mesma transação. O
  papel `abako_app` perde o INSERT direto nas tabelas de versão (completa o ADR 036).
- Erros com SQLSTATE próprios: AB404 (não encontrado), AB409 (versão desatualizada),
  AB410 (nome de conta repetido), AB422 (regra violada). A API traduz em HTTP.
"""

from alembic import op

revision = "0005"
down_revision = "0004"
branch_labels = None
depends_on = None

TIPOS_CONTA = "'corrente', 'reserva', 'investimento', 'beneficio'"
TIPOS_LANCAMENTO = (
    "'debito', 'credito', 'receita', 'transferencia', 'investimento', 'repasse', 'rendimento'"
)


def upgrade() -> None:
    # O tipo de lançamentos antigos seria deduzido do sinal: aceitável só no banco de teste,
    # que se chama `tst` (db/alvo.py; o CI usa o mesmo nome).
    # Fora do `tst` (o `prd` não tinha caminho de lançamento antes da 0005), aborta se houver
    # algum, para ninguém ter o histórico reclassificado sem revisar.
    op.execute(
        """
        DO $$
        BEGIN
            IF current_database() <> 'tst' AND EXISTS (SELECT 1 FROM transacao_versao) THEN
                RAISE EXCEPTION USING MESSAGE =
                    '0005: o banco já tem lançamentos; o tipo deles não pode ser deduzido '
                    'sozinho. Revise com o usuário antes de migrar (ADR 042).';
            END IF;
        END $$
        """
    )

    # ---------- contas ----------
    op.execute("ALTER TABLE conta_versao ADD COLUMN tipo text NOT NULL DEFAULT 'corrente'")
    op.execute("UPDATE conta_versao SET tipo = 'beneficio' WHERE conta_beneficio")
    op.execute(
        f"ALTER TABLE conta_versao ADD CONSTRAINT conta_versao_tipo_ck "
        f"CHECK (tipo IN ({TIPOS_CONTA}))"
    )
    op.execute(
        "ALTER TABLE conta_versao ADD CONSTRAINT conta_versao_beneficio_ck "
        "CHECK (conta_beneficio = (tipo = 'beneficio'))"
    )
    op.execute("ALTER TABLE conta_versao ADD COLUMN conta_mae_id bigint")
    op.execute(
        "ALTER TABLE conta_versao ADD CONSTRAINT conta_versao_mae_ck "
        "CHECK (conta_mae_id IS NULL OR tipo IN ('reserva', 'investimento'))"
    )

    # ---------- lançamentos ----------
    op.execute("ALTER TABLE transacao_versao ADD COLUMN tipo text")
    # Linhas antigas (só existem em teste; o prd não tinha lançamento): sinal define o tipo.
    op.execute(
        "UPDATE transacao_versao SET tipo = CASE WHEN valor < 0 THEN 'debito' ELSE 'receita' END"
    )
    op.execute("ALTER TABLE transacao_versao ALTER COLUMN tipo SET NOT NULL")
    op.execute("ALTER TABLE transacao_versao ADD COLUMN perna smallint NOT NULL DEFAULT 1")
    op.execute("ALTER TABLE transacao_versao ADD COLUMN bruto numeric(14, 2)")
    op.execute("ALTER TABLE transacao_versao ADD COLUMN imposto numeric(14, 2)")
    op.execute("ALTER TABLE transacao_versao ADD COLUMN hash_corpo text")
    op.execute(
        f"ALTER TABLE transacao_versao ADD CONSTRAINT transacao_versao_tipo_ck "
        f"CHECK (tipo IN ({TIPOS_LANCAMENTO}))"
    )
    op.execute(
        "ALTER TABLE transacao_versao ADD CONSTRAINT transacao_versao_perna_ck CHECK ("
        "  perna = 1 OR (perna = 2 AND tipo IN ('transferencia', 'investimento')))"
    )
    op.execute(
        "ALTER TABLE transacao_versao ADD CONSTRAINT transacao_versao_sinal_ck CHECK ("
        "     (tipo = 'debito' AND valor < 0)"
        "  OR (tipo = 'receita' AND valor > 0)"
        "  OR (tipo IN ('transferencia', 'investimento')"
        "      AND ((perna = 1 AND valor < 0) OR (perna = 2 AND valor > 0)))"
        "  OR (tipo = 'rendimento' AND valor > 0)"
        "  OR tipo IN ('credito', 'repasse'))"  # regras próprias nas SPECs 005 e 007
    )
    op.execute(
        "ALTER TABLE transacao_versao ADD CONSTRAINT transacao_versao_rendimento_ck CHECK ("
        "  CASE WHEN tipo = 'rendimento'"
        "       THEN bruto IS NOT NULL AND imposto IS NOT NULL AND bruto > 0"
        "            AND imposto >= 0 AND imposto < bruto AND valor = bruto - imposto"
        "       ELSE bruto IS NULL AND imposto IS NULL END)"
    )
    # Unicidades passam a incluir a perna (as duas pernas têm o mesmo id e a mesma versão).
    op.execute(
        "ALTER TABLE transacao_versao "
        "DROP CONSTRAINT transacao_versao_user_id_transacao_id_versao_key"
    )
    op.execute(
        "ALTER TABLE transacao_versao ADD CONSTRAINT transacao_versao_id_versao_perna_key "
        "UNIQUE (user_id, transacao_id, versao, perna)"
    )
    op.execute("DROP INDEX transacao_versao_vigente_uq")
    op.execute(
        "CREATE UNIQUE INDEX transacao_versao_vigente_uq ON transacao_versao "
        "(user_id, transacao_id, perna) WHERE vigente"
    )
    # A chave de idempotência fica só na perna 1 da versão 1 (a UNIQUE da 0002 continua).
    op.execute(
        "ALTER TABLE transacao_versao ADD CONSTRAINT transacao_versao_chave_ck "
        "CHECK (chave_idempotencia IS NULL OR (perna = 1 AND versao = 1))"
    )

    # Mesmas colunas da 0004 e as novas no fim (CREATE OR REPLACE só acrescenta).
    op.execute(
        """
        CREATE OR REPLACE VIEW transacao_vigente WITH (security_invoker = true) AS
        SELECT id, user_id, transacao_id, versao, conta_id, data_transacao, valor, descricao,
               tipo, perna, bruto, imposto
        FROM transacao_versao
        WHERE vigente AND NOT excluida
        """
    )
    # Um lançamento por linha (as duas pernas juntas), com o valor positivo como foi digitado.
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

    op.execute(
        """
        CREATE FUNCTION abako_erro(p_codigo text, p_mensagem text) RETURNS void
        LANGUAGE plpgsql AS $$
        BEGIN
            RAISE EXCEPTION USING ERRCODE = p_codigo, MESSAGE = p_mensagem;
        END
        $$
        """
    )

    op.execute(
        """
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
    )

    op.execute(
        """
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
    )

    op.execute(
        """
        CREATE FUNCTION lancamento_excluir(p_user bigint, p_transacao bigint, p_versao integer)
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
    )

    # INV-01 no próprio esquema: ao fim da transação, cada versão de lançamento tem 1 perna
    # (2 em transferência/investimento, uma em cada conta, soma zero), todas com o mesmo tipo,
    # data e marca de exclusão. Vale até para o dono do banco.
    op.execute(
        """
        CREATE FUNCTION transacao_pernas_ck() RETURNS trigger
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
    )
    op.execute(
        "CREATE CONSTRAINT TRIGGER transacao_pernas_ck AFTER INSERT OR UPDATE ON transacao_versao "
        "DEFERRABLE INITIALLY DEFERRED FOR EACH ROW EXECUTE FUNCTION transacao_pernas_ck()"
    )

    # ---------- papéis ----------
    op.execute("REVOKE INSERT ON conta_versao, transacao_versao FROM abako_app")
    # Os ids lógicos agora saem só das funções (do dono): a aplicação não consome sequência.
    op.execute("REVOKE USAGE ON SEQUENCE conta_id_seq, transacao_id_seq FROM abako_app")
    op.execute("GRANT SELECT ON lancamento_vigente TO abako_app, abako_pipeline")
    for assinatura in (
        "abako_erro(text, text)",
        "conta_gravar(bigint, bigint, integer, text, text, bigint)",
        "lancamento_gravar(bigint, bigint, integer, text, date, numeric, bigint, bigint, "
        "numeric, numeric, text, text, text)",
        "lancamento_excluir(bigint, bigint, integer)",
    ):
        op.execute(f"REVOKE ALL ON FUNCTION {assinatura} FROM PUBLIC")
    for assinatura in (
        "conta_gravar(bigint, bigint, integer, text, text, bigint)",
        "lancamento_gravar(bigint, bigint, integer, text, date, numeric, bigint, bigint, "
        "numeric, numeric, text, text, text)",
        "lancamento_excluir(bigint, bigint, integer)",
    ):
        op.execute(f"GRANT EXECUTE ON FUNCTION {assinatura} TO abako_app")


def downgrade() -> None:
    # Irreversível com dados (ADR 042): voltar apagaria pernas de transferência, bruto/imposto
    # e o tipo das contas. Com dado assim, o caminho é restaurar o backup anterior à 0005.
    op.execute(
        """
        DO $$
        BEGIN
            IF EXISTS (SELECT 1 FROM transacao_versao
                       WHERE perna = 2 OR tipo NOT IN ('debito', 'receita'))
               OR EXISTS (SELECT 1 FROM conta_versao
                          WHERE tipo IN ('reserva', 'investimento') OR conta_mae_id IS NOT NULL)
            THEN
                RAISE EXCEPTION USING MESSAGE =
                    '0005: há lançamentos ou contas que só existem nesta versão; o downgrade '
                    'apagaria dados. Restaure o backup anterior à 0005 (ADR 042).';
            END IF;
        END $$
        """
    )
    op.execute("DROP TRIGGER IF EXISTS transacao_pernas_ck ON transacao_versao")
    op.execute("DROP FUNCTION IF EXISTS transacao_pernas_ck()")
    op.execute("GRANT USAGE ON SEQUENCE conta_id_seq, transacao_id_seq TO abako_app")
    op.execute("GRANT INSERT ON conta_versao, transacao_versao TO abako_app")
    op.execute("DROP FUNCTION lancamento_excluir(bigint, bigint, integer)")
    op.execute(
        "DROP FUNCTION lancamento_gravar(bigint, bigint, integer, text, date, numeric, bigint, "
        "bigint, numeric, numeric, text, text, text)"
    )
    op.execute("DROP FUNCTION conta_gravar(bigint, bigint, integer, text, text, bigint)")
    op.execute("DROP FUNCTION abako_erro(text, text)")
    op.execute("DROP VIEW lancamento_vigente")
    # A view da 0004 não tem as colunas novas: recria como era.
    op.execute("DROP VIEW transacao_vigente")
    op.execute(
        """
        CREATE VIEW transacao_vigente WITH (security_invoker = true) AS
        SELECT id, user_id, transacao_id, versao, conta_id, data_transacao, valor, descricao
        FROM transacao_versao
        WHERE vigente AND NOT excluida
        """
    )
    op.execute("GRANT SELECT ON transacao_vigente TO abako_app, abako_pipeline")
    op.execute("ALTER TABLE transacao_versao DROP CONSTRAINT transacao_versao_chave_ck")
    op.execute("DROP INDEX transacao_versao_vigente_uq")
    op.execute(
        "CREATE UNIQUE INDEX transacao_versao_vigente_uq ON transacao_versao "
        "(user_id, transacao_id) WHERE vigente"
    )
    op.execute("ALTER TABLE transacao_versao DROP CONSTRAINT transacao_versao_id_versao_perna_key")
    op.execute(
        "ALTER TABLE transacao_versao ADD CONSTRAINT "
        "transacao_versao_user_id_transacao_id_versao_key UNIQUE (user_id, transacao_id, versao)"
    )
    for coluna in ("hash_corpo", "imposto", "bruto", "perna", "tipo"):
        op.execute(f"ALTER TABLE transacao_versao DROP COLUMN {coluna}")
    op.execute("ALTER TABLE conta_versao DROP COLUMN conta_mae_id")
    op.execute("ALTER TABLE conta_versao DROP CONSTRAINT conta_versao_beneficio_ck")
    op.execute("ALTER TABLE conta_versao DROP COLUMN tipo")
