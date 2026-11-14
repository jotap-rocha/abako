"""Configuração do pipeline: alvo, URL do papel somente leitura e pasta do arquivo analítico.

Nada de senha ou caminho no código: tudo vem do ambiente (ADR 018) e passa pelo guarda de alvo.
"""

from __future__ import annotations

import os
from collections.abc import Mapping
from dataclasses import dataclass, field
from datetime import date
from pathlib import Path
from zoneinfo import ZoneInfo

from db.alvo import (
    BANCO_PRD,
    BANCO_TST,
    RAIZ,
    USUARIO_PIPELINE,
    VAR_CONFIRMA_PRD,
    VAR_URL_PIPELINE,
    VAR_URL_PIPELINE_PRD,
    AlvoInvalido,
    url_psycopg,
    verificar_url_papel,
    verificar_url_papel_prd,
)

VAR_DIR = "ABAKO_ANALITICO_DIR"
FUSO = ZoneInfo("America/Sao_Paulo")


class ConfigInvalida(Exception):
    """Configuração do pipeline recusada antes de qualquer conexão ou escrita."""


@dataclass(frozen=True)
class Config:
    ambiente: str  # tst | prd
    url: str = field(repr=False)  # libpq, do papel abako_pipeline; nunca no repr (senha)
    diretorio: Path
    hoje: date
    usuarios: tuple[int, ...] | None = None  # None = todos

    @property
    def arquivo(self) -> Path:
        return self.diretorio / f"analitico_{self.ambiente}.duckdb"


def hoje_civil() -> date:
    """Data civil em America/Sao_Paulo (nunca UTC)."""
    from datetime import datetime

    return datetime.now(FUSO).date()


def diretorio_padrao(environ: Mapping[str, str]) -> Path:
    base = environ.get("LOCALAPPDATA")
    if base:
        return Path(base) / "abako" / "analitico"
    return Path.home() / ".local" / "share" / "abako" / "analitico"


def verificar_diretorio(diretorio: Path) -> Path:
    """Recusa pasta dentro do repositório: o analítico nunca é versionado."""
    resolvido = diretorio.expanduser().resolve()
    if resolvido == RAIZ or RAIZ in resolvido.parents:
        raise ConfigInvalida(f"{VAR_DIR} aponta para dentro do repositório; use uma pasta externa")
    return resolvido


def caminho_arquivo(environ: Mapping[str, str], alvo: str, diretorio: Path | None = None) -> Path:
    """Caminho do arquivo analítico do alvo, sem tocar no banco (usado pela leitura)."""
    if alvo not in (BANCO_TST, BANCO_PRD):
        raise ConfigInvalida(f"alvo inválido: {alvo!r} (tst|prd)")
    bruto = diretorio or (Path(environ[VAR_DIR]) if environ.get(VAR_DIR) else None)
    return verificar_diretorio(bruto or diretorio_padrao(environ)) / f"analitico_{alvo}.duckdb"


def montar(
    environ: Mapping[str, str],
    alvo: str,
    hoje: date | None = None,
    usuarios: tuple[int, ...] | None = None,
    diretorio: Path | None = None,
) -> Config:
    """Decide o alvo (tst padrão; prd só com confirmação humana) e valida a URL do papel."""
    try:
        if alvo == BANCO_TST:
            var = VAR_URL_PIPELINE
            url = environ.get(var, "")
            verificar_url_papel(url, var, USUARIO_PIPELINE)
        elif alvo == BANCO_PRD:
            if environ.get(VAR_CONFIRMA_PRD) != "sim":
                raise AlvoInvalido(
                    "pipeline em prd exige confirmação humana: ABAKO_CONFIRMA_PRD=sim no "
                    "ambiente do processo (ADR 019)"
                )
            var = VAR_URL_PIPELINE_PRD
            url = environ.get(var, "")
            verificar_url_papel_prd(url, var, USUARIO_PIPELINE)
        else:
            raise AlvoInvalido(f"alvo inválido: {alvo!r} (tst|prd)")
    except AlvoInvalido as exc:
        raise ConfigInvalida(str(exc)) from exc
    except ValueError:
        # urlsplit pode citar a URL (com senha) na mensagem: não propagar nem encadear
        raise ConfigInvalida("URL do banco do pipeline malformada") from None
    bruto = diretorio or (Path(environ[VAR_DIR]) if environ.get(VAR_DIR) else None)
    pasta = verificar_diretorio(bruto or diretorio_padrao(environ))
    return Config(alvo, url_psycopg(url), pasta, hoje or hoje_civil(), usuarios)


def ambiente_do_processo() -> Mapping[str, str]:
    return os.environ
