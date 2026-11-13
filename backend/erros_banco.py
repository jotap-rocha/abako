"""Tradução dos erros de regra das funções do banco (SQLSTATE próprios, ADR 042) para HTTP.

A mensagem vem das funções da migração 0005: texto curto nosso, sem valor nem dado pessoal.
O código (AB404, AB409, AB410, AB422) vai também no cabeçalho `X-Abako-Erro`, para o front
distinguir, por exemplo, "nome repetido" de "versão desatualizada" (os dois são 409) sem
depender do texto. Qualquer outro erro de banco segue adiante (500 sem detalhe, como antes).
"""

from __future__ import annotations

import unicodedata
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

import psycopg
from fastapi import HTTPException, status

CABECALHO_CODIGO = "X-Abako-Erro"
STATUS_POR_CODIGO = {
    "AB404": status.HTTP_404_NOT_FOUND,
    "AB409": status.HTTP_409_CONFLICT,
    "AB410": status.HTTP_409_CONFLICT,
    "AB422": status.HTTP_422_UNPROCESSABLE_CONTENT,
}


@asynccontextmanager
async def regras_do_banco() -> AsyncIterator[None]:
    """Envolve a chamada a uma função de escrita: erro de regra vira HTTPException."""
    try:
        yield
    except psycopg.Error as exc:
        codigo = exc.sqlstate
        if codigo not in STATUS_POR_CODIGO:
            raise
        mensagem = exc.diag.message_primary or "operação recusada"
        raise HTTPException(
            STATUS_POR_CODIGO[codigo], mensagem, headers={CABECALHO_CODIGO: codigo}
        ) from None


def mes_valido(mes: str) -> str:
    """Barra o que o banco nem chegaria a ler (muito longo; NUL e controle dariam 500 no driver)
    com o mesmo 422/AB422 literal que o banco devolve para formato inválido (`mes_inicio`)."""
    if len(mes) > 16 or any(unicodedata.category(c) == "Cc" for c in mes):
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_CONTENT,
            "o mês precisa estar no formato AAAA-MM",
            headers={CABECALHO_CODIGO: "AB422"},
        )
    return mes
