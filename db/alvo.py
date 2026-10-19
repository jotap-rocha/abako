"""Guarda de alvo do banco (ADR 014/021): a suíte e as migrações só tocam o `tst`.

A verificação estática da URL roda antes de qualquer conexão.
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any
from urllib.parse import urlsplit

RAIZ = Path(__file__).resolve().parent.parent
HOSTS_LOCAIS = {"127.0.0.1", "localhost"}
PORTA_ABAKO = 5433
BANCO_TST = "tst"
VAR_URL_TST = "ABAKO_DB_MIGRATE_URL_TST"


class AlvoInvalido(Exception):
    """A conexão não é a do banco `tst` do contêiner dedicado."""


def carregar_env(caminho: Path | None = None) -> None:
    """Carrega `KEY=VALUE` de `.env` para `os.environ` sem sobrescrever o que já existe.

    Roda só no processo do usuário (testes/Alembic); nunca imprime valores.
    Comentário inline exige espaço antes do `#`.
    """
    arq = caminho or RAIZ / ".env"
    if not arq.is_file():
        return
    for bruta in arq.read_text(encoding="utf-8").splitlines():
        linha = bruta.strip()
        if not linha or linha.startswith("#") or "=" not in linha:
            continue
        chave, _, valor = linha.partition("=")
        valor = valor.strip()
        if len(valor) >= 2 and valor[0] in {'"', "'"} and valor.endswith(valor[0]):
            valor = valor[1:-1]
        else:
            valor = valor.split(" #", 1)[0].strip()
        os.environ.setdefault(chave.strip(), valor)


def verificar_url_tst(url: str) -> None:
    """Levanta `AlvoInvalido` se a URL não for `127.0.0.1|localhost:5433/tst`."""
    if not url:
        raise AlvoInvalido(f"{VAR_URL_TST} não definida: a suíte só roda contra o banco `tst`")
    partes = urlsplit(url)
    banco = partes.path.lstrip("/")
    try:
        porta = partes.port
    except ValueError as exc:
        raise AlvoInvalido("porta inválida na URL do banco") from exc
    if partes.hostname not in HOSTS_LOCAIS:
        raise AlvoInvalido(f"host {partes.hostname!r} não é local (esperado 127.0.0.1)")
    if porta != PORTA_ABAKO:
        raise AlvoInvalido(f"porta {porta} != {PORTA_ABAKO} (a 5432 é de outro projeto)")
    if banco != BANCO_TST:
        raise AlvoInvalido(f"banco {banco!r} != 'tst': a suíte só roda contra o banco `tst`")


def verificar_ambiente_tst() -> str:
    """Valida `ABAKO_ENV` (padrão tst) e a URL de `tst`; devolve a URL."""
    amb = os.environ.get("ABAKO_ENV", "tst")
    if amb != "tst":
        raise AlvoInvalido(f"ABAKO_ENV={amb!r}: a suíte só roda com ABAKO_ENV=tst")
    url = os.environ.get(VAR_URL_TST, "")
    verificar_url_tst(url)
    return url


def verificar_conexao_tst(conn: Any) -> None:
    """Confere no servidor que `current_database()` é `tst`."""
    banco = conn.execute("SELECT current_database()").fetchone()[0]
    if banco != BANCO_TST:
        raise AlvoInvalido(f"conectado em {banco!r}, esperado 'tst'")


def url_psycopg(url: str) -> str:
    """URL no formato libpq (sem sufixo de driver SQLAlchemy)."""
    return url.replace("postgresql+psycopg://", "postgresql://", 1)


def url_sqlalchemy(url: str) -> str:
    """URL com o driver psycopg (v3) para o SQLAlchemy/Alembic."""
    if url.startswith("postgresql://"):
        return url.replace("postgresql://", "postgresql+psycopg://", 1)
    return url
