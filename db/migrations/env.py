"""Alembic em SQL puro (ADR 025): sem autogenerate, sem modelos ORM.

Alvo por ABAKO_ENV (padrão `tst`). `prd` exige ABAKO_CONFIRMA_PRD=sim (confirmação humana,
ADR 019) e a URL ABAKO_DB_MIGRATE_URL_PRD; o agente não aplica migração em `prd`.
"""

from __future__ import annotations

import os

from alembic import context
from sqlalchemy import create_engine, text

from db.alvo import (
    AlvoInvalido,
    carregar_env,
    url_sqlalchemy,
    verificar_url_tst,
)

carregar_env()


def _url_alvo() -> tuple[str, str]:
    amb = os.environ.get("ABAKO_ENV", "tst")
    if amb == "tst":
        url = os.environ.get("ABAKO_DB_MIGRATE_URL_TST", "")
        verificar_url_tst(url)
        return amb, url
    if amb == "prd":
        if os.environ.get("ABAKO_CONFIRMA_PRD") != "sim":
            raise AlvoInvalido(
                "migração em prd exige confirmação humana: ABAKO_CONFIRMA_PRD=sim "
                "(e backup recente, ADR 019/025)"
            )
        url = os.environ.get("ABAKO_DB_MIGRATE_URL_PRD", "")
        if not url:
            raise AlvoInvalido("ABAKO_DB_MIGRATE_URL_PRD não definida")
        return amb, url
    raise AlvoInvalido(f"ABAKO_ENV inválido: {amb!r} (tst|prd)")


def run_migrations_online() -> None:
    amb, url = _url_alvo()
    engine = create_engine(url_sqlalchemy(url))
    with engine.connect() as connection:
        if amb == "tst":
            banco = connection.execute(text("SELECT current_database()")).scalar()
            if banco != "tst":
                raise AlvoInvalido(f"conectado em {banco!r}, esperado 'tst'")
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
