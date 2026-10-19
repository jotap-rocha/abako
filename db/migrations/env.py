"""Alembic em SQL puro (ADR 025): sem autogenerate, sem modelos ORM.

Alvo por ABAKO_ENV (padrão `tst`), decidido em `db.alvo.decidir_alvo`. `prd` exige
ABAKO_CONFIRMA_PRD=sim no ambiente do processo (nunca lido do arquivo de variáveis; ADR 019);
o agente não aplica migração em `prd`.
"""

from __future__ import annotations

import os

from alembic import context
from sqlalchemy import create_engine, text

from db.alvo import (
    AlvoInvalido,
    carregar_env,
    decidir_alvo,
    url_sqlalchemy,
    verificar_banco_conectado,
)

carregar_env()


def run_migrations_online() -> None:
    amb, url = decidir_alvo(os.environ)
    engine = create_engine(url_sqlalchemy(url))
    with engine.connect() as connection:
        banco = connection.execute(text("SELECT current_database()")).scalar()
        verificar_banco_conectado(amb, banco)
        # Encerra a transação aberta pelo SELECT acima (autobegin do SQLAlchemy 2.0);
        # sem isso o Alembic não abre a sua própria e a migração nunca é commitada.
        connection.rollback()
        context.configure(connection=connection, target_metadata=None)
        with context.begin_transaction():
            context.run_migrations()
    engine.dispose()


if context.is_offline_mode():
    raise AlvoInvalido("modo offline (--sql) não suportado: migrações rodam contra o banco")
run_migrations_online()
