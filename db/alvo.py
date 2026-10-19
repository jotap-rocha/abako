"""Guarda de alvo do banco (ADR 014/021): a suíte e as migrações só tocam o banco decidido.

A verificação estática da URL roda antes de qualquer conexão.
"""

from __future__ import annotations

import os
from collections.abc import Mapping
from pathlib import Path
from typing import Any
from urllib.parse import urlsplit

RAIZ = Path(__file__).resolve().parent.parent
HOSTS_LOCAIS = {"127.0.0.1", "localhost"}
PORTA_ABAKO = 5433
BANCO_TST = "tst"
BANCO_PRD = "prd"
VAR_URL_TST = "ABAKO_DB_MIGRATE_URL_TST"
VAR_URL_PRD = "ABAKO_DB_MIGRATE_URL_PRD"
VAR_CONFIRMA_PRD = "ABAKO_CONFIRMA_PRD"
# Confirmação humana não pode vir de arquivo: só do ambiente real do processo.
NAO_IMPORTAR_DO_ENV = {VAR_CONFIRMA_PRD}


class AlvoInvalido(Exception):
    """A conexão não é a do banco esperado do contêiner dedicado."""


def carregar_env(caminho: Path | None = None) -> None:
    """Carrega `KEY=VALUE` de `.env` para `os.environ` sem sobrescrever o que já existe.

    Roda só no processo do usuário (testes/Alembic); nunca imprime valores.
    Comentário inline exige espaço antes do `#`. Chaves em `NAO_IMPORTAR_DO_ENV` são ignoradas.
    """
    arq = caminho or RAIZ / ".env"
    if not arq.is_file():
        return
    for bruta in arq.read_text(encoding="utf-8").splitlines():
        linha = bruta.strip()
        if not linha or linha.startswith("#") or "=" not in linha:
            continue
        chave, _, valor = linha.partition("=")
        chave = chave.strip()
        if chave in NAO_IMPORTAR_DO_ENV:
            continue
        valor = valor.strip()
        if len(valor) >= 2 and valor[0] in {'"', "'"} and valor.endswith(valor[0]):
            valor = valor[1:-1]
        else:
            valor = valor.split(" #", 1)[0].strip()
        os.environ.setdefault(chave, valor)


def _verificar_url(url: str, banco_esperado: str, var: str) -> None:
    if not url:
        raise AlvoInvalido(f"{var} não definida")
    partes = urlsplit(url)
    if partes.query:
        raise AlvoInvalido("URL com query string não é aceita (poderia trocar host/banco)")
    banco = partes.path.lstrip("/")
    try:
        porta = partes.port
    except ValueError as exc:
        raise AlvoInvalido("porta inválida na URL do banco") from exc
    if partes.hostname not in HOSTS_LOCAIS:
        raise AlvoInvalido(f"host {partes.hostname!r} não é local (esperado 127.0.0.1)")
    if porta != PORTA_ABAKO:
        raise AlvoInvalido(f"porta {porta} != {PORTA_ABAKO} (a 5432 é de outro projeto)")
    if banco != banco_esperado:
        raise AlvoInvalido(f"banco {banco!r} != {banco_esperado!r}")


def verificar_url_tst(url: str) -> None:
    """Levanta `AlvoInvalido` se a URL não for `127.0.0.1|localhost:5433/tst` (sem query)."""
    _verificar_url(url, BANCO_TST, VAR_URL_TST)


def verificar_url_prd(url: str) -> None:
    """Idem para `prd`; só usada após a confirmação humana (ADR 019)."""
    _verificar_url(url, BANCO_PRD, VAR_URL_PRD)


def decidir_alvo(environ: Mapping[str, str]) -> tuple[str, str]:
    """Decide (ambiente, url) das migrações sem conectar em nada.

    `prd` exige ABAKO_CONFIRMA_PRD=sim vindo do ambiente real do processo.
    """
    amb = environ.get("ABAKO_ENV", BANCO_TST)
    if amb == BANCO_TST:
        url = environ.get(VAR_URL_TST, "")
        verificar_url_tst(url)
        return amb, url
    if amb == BANCO_PRD:
        if environ.get(VAR_CONFIRMA_PRD) != "sim":
            raise AlvoInvalido(
                "migração em prd exige confirmação humana: ABAKO_CONFIRMA_PRD=sim "
                "no ambiente do processo (e backup recente, ADR 019/025)"
            )
        url = environ.get(VAR_URL_PRD, "")
        verificar_url_prd(url)
        return amb, url
    raise AlvoInvalido(f"ABAKO_ENV inválido: {amb!r} (tst|prd)")


def verificar_ambiente_tst() -> str:
    """Valida `ABAKO_ENV` (padrão tst) e a URL de `tst`; devolve a URL."""
    amb = os.environ.get("ABAKO_ENV", BANCO_TST)
    if amb != BANCO_TST:
        raise AlvoInvalido(f"ABAKO_ENV={amb!r}: a suíte só roda com ABAKO_ENV=tst")
    url = os.environ.get(VAR_URL_TST, "")
    verificar_url_tst(url)
    return url


def verificar_banco_conectado(esperado: str, banco: object) -> None:
    """Confere o `current_database()` devolvido pelo servidor contra o ambiente decidido."""
    if banco != esperado:
        raise AlvoInvalido(f"conectado em {banco!r}, esperado {esperado!r}")


def verificar_conexao_tst(conn: Any) -> None:
    """Confere no servidor que `current_database()` é `tst`."""
    verificar_banco_conectado(BANCO_TST, conn.execute("SELECT current_database()").fetchone()[0])


def url_psycopg(url: str) -> str:
    """URL no formato libpq (sem sufixo de driver SQLAlchemy)."""
    return url.replace("postgresql+psycopg://", "postgresql://", 1)


def url_sqlalchemy(url: str) -> str:
    """URL com o driver psycopg (v3) para o SQLAlchemy/Alembic."""
    if url.startswith("postgresql://"):
        return url.replace("postgresql://", "postgresql+psycopg://", 1)
    return url
