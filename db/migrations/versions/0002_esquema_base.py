"""esquema base do ledger: usuario, conta_versao, transacao_versao e grants dos papéis

Revision ID: 0002
Revises: 0001

SQL puro (ADR 025). As tabelas de versão são append-only para a aplicação (ADR 006/036):
o papel `abako_app` só recebe SELECT/INSERT. Os papéis são do cluster (compartilhados por
`tst` e `prd`) e criados fora da migração por `python -m scripts.criar_papeis`, porque o dono
do banco não tem CREATEROLE e nenhuma senha pode viver no código.
"""

from alembic import op

revision = "0002"
down_revision = "0001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        """
        DO $$
        DECLARE papel text;
        BEGIN
            FOREACH papel IN ARRAY ARRAY['abako_app', 'abako_pipeline'] LOOP
                IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = papel) THEN
                    RAISE EXCEPTION USING MESSAGE =
                        'papel ' || papel || ' inexistente: rode python -m scripts.criar_papeis';
                END IF;
            END LOOP;
        END $$
        """
    )

    op.execute(
        """
        CREATE TABLE usuario (
            user_id   bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
            login     text NOT NULL UNIQUE,
            criado_em timestamptz NOT NULL DEFAULT now()
        )
        """
    )

    # Identidade lógica da entidade (conta_id) é estável entre versões; `id` é da linha.
    op.execute("CREATE SEQUENCE conta_id_seq")
    op.execute(
        """
        CREATE TABLE conta_versao (
            id             bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
            user_id        bigint  NOT NULL REFERENCES usuario (user_id),
            conta_id       bigint  NOT NULL DEFAULT nextval('conta_id_seq'),
            versao         integer NOT NULL DEFAULT 1 CHECK (versao >= 1),
            vigente        boolean NOT NULL DEFAULT true,
            excluida       boolean NOT NULL DEFAULT false,
            nome           text    NOT NULL,
            conta_beneficio boolean NOT NULL DEFAULT false,
            criado_em      timestamptz NOT NULL DEFAULT now(),
            UNIQUE (user_id, conta_id, versao)
        )
        """
    )
    op.execute(
        "CREATE UNIQUE INDEX conta_versao_vigente_uq ON conta_versao (user_id, conta_id) "
        "WHERE vigente"
    )

    op.execute("CREATE SEQUENCE transacao_id_seq")
    # A chave de idempotência só é gravada na versão que cria a transação; versões
    # seguintes a deixam NULL (NULLs não colidem no índice único).
    op.execute(
        """
        CREATE TABLE transacao_versao (
            id                 bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
            user_id            bigint  NOT NULL REFERENCES usuario (user_id),
            transacao_id       bigint  NOT NULL DEFAULT nextval('transacao_id_seq'),
            versao             integer NOT NULL DEFAULT 1 CHECK (versao >= 1),
            vigente            boolean NOT NULL DEFAULT true,
            excluida           boolean NOT NULL DEFAULT false,
            conta_id           bigint  NOT NULL,
            data_transacao     date    NOT NULL,
            valor              numeric(14, 2) NOT NULL,
            descricao          text,
            chave_idempotencia text,
            criado_em          timestamptz NOT NULL DEFAULT now(),
            UNIQUE (user_id, transacao_id, versao),
            UNIQUE (user_id, chave_idempotencia)
        )
        """
    )
    op.execute(
        "CREATE UNIQUE INDEX transacao_versao_vigente_uq ON transacao_versao "
        "(user_id, transacao_id) WHERE vigente"
    )

    op.execute(
        """
        DO $$
        BEGIN
            EXECUTE 'GRANT CONNECT ON DATABASE ' || quote_ident(current_database())
                || ' TO abako_app, abako_pipeline';
        END $$
        """
    )
    op.execute("GRANT USAGE ON SCHEMA public TO abako_app, abako_pipeline")
    # app: só SELECT/INSERT (sem UPDATE/DELETE); pipeline: só leitura.
    op.execute("GRANT SELECT, INSERT ON usuario, conta_versao, transacao_versao TO abako_app")
    op.execute("GRANT USAGE ON SEQUENCE conta_id_seq, transacao_id_seq TO abako_app")
    op.execute("GRANT SELECT ON usuario, conta_versao, transacao_versao TO abako_pipeline")


def downgrade() -> None:
    op.execute(
        """
        DO $$
        DECLARE papel text;
        BEGIN
            FOREACH papel IN ARRAY ARRAY['abako_app', 'abako_pipeline'] LOOP
                IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = papel) THEN
                    EXECUTE 'REVOKE CONNECT ON DATABASE ' || quote_ident(current_database())
                        || ' FROM ' || quote_ident(papel);
                END IF;
            END LOOP;
        END $$
        """
    )
    op.execute("DROP TABLE transacao_versao")
    op.execute("DROP TABLE conta_versao")
    op.execute("DROP SEQUENCE transacao_id_seq")
    op.execute("DROP SEQUENCE conta_id_seq")
    op.execute("DROP TABLE usuario")
