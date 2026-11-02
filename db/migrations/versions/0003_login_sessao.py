"""login e sessão: credencial (hash Argon2id) e sessao (hash do token + token CSRF)

Revision ID: 0003
Revises: 0002

SQL puro (ADR 025). Decisões no ADR 038:
- `credencial` é só leitura para `abako_app`: senha se cria e se troca pelo comando local
  (`python -m backend.cli`), que conecta como dono do banco. Nenhuma rota web grava senha.
- `sessao` guarda o SHA-256 do token do cookie, nunca o token. `abako_app` pode apagar
  (logout e expiração): não é tabela de versão do ledger (ADR 036).
"""

from alembic import op

revision = "0003"
down_revision = "0002"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        """
        CREATE TABLE credencial (
            user_id       bigint PRIMARY KEY REFERENCES usuario (user_id),
            senha_hash    text NOT NULL CHECK (senha_hash LIKE '$argon2id$%'),
            atualizada_em timestamptz NOT NULL DEFAULT now()
        )
        """
    )
    op.execute(
        """
        CREATE TABLE sessao (
            sessao_id  bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
            user_id    bigint NOT NULL REFERENCES usuario (user_id),
            token_hash bytea  NOT NULL UNIQUE CHECK (octet_length(token_hash) = 32),
            csrf_token text   NOT NULL,
            criada_em  timestamptz NOT NULL DEFAULT now(),
            expira_em  timestamptz NOT NULL,
            CHECK (expira_em > criada_em)
        )
        """
    )
    op.execute("CREATE INDEX sessao_user_id_idx ON sessao (user_id)")

    op.execute("GRANT SELECT ON credencial TO abako_app")
    op.execute("GRANT SELECT, INSERT, DELETE ON sessao TO abako_app")


def downgrade() -> None:
    op.execute("DROP TABLE sessao")
    op.execute("DROP TABLE credencial")
