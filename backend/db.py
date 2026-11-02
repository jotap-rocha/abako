"""Conexão por requisição com o papel `abako_app`."""

from __future__ import annotations

import sys
from collections.abc import AsyncIterator

import psycopg
from fastapi import Request

if sys.platform == "win32":
    import asyncio

    # psycopg assíncrono não roda no ProactorEventLoop, o padrão do Windows.
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())


async def conexao(request: Request) -> AsyncIterator[psycopg.AsyncConnection]:
    """Commit ao fim da requisição; qualquer exceção desfaz."""
    url = request.app.state.settings.db_app_url.get_secret_value()
    async with await psycopg.AsyncConnection.connect(url) as conn:
        yield conn
