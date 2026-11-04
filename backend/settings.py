"""Configuração do backend só via pydantic-settings (ADR 018); nenhum `os.environ` solto."""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import Literal
from urllib.parse import urlsplit, urlunsplit

from pydantic import Field, SecretStr, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

HOSTS_PERMITIDOS = ("abako.localhost", "localhost", "127.0.0.1")
RAIZ = Path(__file__).resolve().parent.parent


class Settings(BaseSettings):
    """Variáveis `ABAKO_*` do ambiente ou do `.env` (fora do git)."""

    model_config = SettingsConfigDict(
        env_prefix="ABAKO_", env_file=".env", extra="ignore", frozen=True
    )

    # Papel `abako_app` (sem UPDATE/DELETE nas tabelas de versão).
    db_app_url: SecretStr
    # `tst` (padrão) ou `prd`. Com `prd` o servidor usa o banco `prd` com o mesmo papel
    # `abako_app`: a URL de `db_app_url` aponta para `tst` e só o nome do banco troca.
    env: Literal["tst", "prd"] = "tst"
    porta: int = 8080
    # Build do front (`npm run build`); ausente = só API.
    frontend_dist: Path = RAIZ / "frontend" / "dist"
    # Host aceito (INV-34, ADR 035); a porta não entra na comparação.
    hosts_permitidos: tuple[str, ...] = HOSTS_PERMITIDOS
    # Origens de navegador aceitas em escrita e no CORS; vazio = derivadas de host + porta.
    origens_permitidas: tuple[str, ...] = ()
    sessao_duracao_s: int = Field(default=8 * 3600, gt=0)
    login_max_falhas: int = Field(default=5, gt=0)
    login_janela_s: int = Field(default=15 * 60, gt=0)

    @field_validator("hosts_permitidos")
    @classmethod
    def _hosts_sem_curinga(cls, v: tuple[str, ...]) -> tuple[str, ...]:
        if not v or any("*" in h for h in v):
            raise ValueError("hosts_permitidos não aceita vazio nem curinga (INV-34)")
        return v

    @field_validator("origens_permitidas")
    @classmethod
    def _origens_locais(cls, v: tuple[str, ...]) -> tuple[str, ...]:
        locais = ("http://localhost", "http://127.0.0.1", "http://abako.localhost")
        if any(not o.startswith(locais) or "*" in o for o in v):
            raise ValueError("origens_permitidas só aceita origens locais explícitas (ADR 031)")
        return v

    @property
    def url_banco(self) -> str:
        """URL do banco do ambiente escolhido (`ABAKO_ENV`)."""
        url = self.db_app_url.get_secret_value()
        if self.env == "tst":
            return url
        partes = urlsplit(url)
        if partes.path != "/tst":
            raise ValueError("ABAKO_ENV=prd espera ABAKO_DB_APP_URL apontando para o banco tst")
        return urlunsplit(partes._replace(path="/prd"))

    @property
    def origens(self) -> tuple[str, ...]:
        if self.origens_permitidas:
            return self.origens_permitidas
        return tuple(f"http://{h}:{self.porta}" for h in self.hosts_permitidos)


@lru_cache
def obter_settings() -> Settings:
    return Settings()  # type: ignore[call-arg]  # db_app_url vem do ambiente
