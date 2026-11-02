"""baseline: função de identificação do banco de teste

Revision ID: 0001
Revises:
"""

from alembic import op

revision = "0001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        """
        CREATE OR REPLACE FUNCTION public.abako_banco_tst() RETURNS boolean
        LANGUAGE sql STABLE AS $$ SELECT current_database() = 'tst' $$
        """
    )


def downgrade() -> None:
    op.execute("DROP FUNCTION IF EXISTS public.abako_banco_tst()")
