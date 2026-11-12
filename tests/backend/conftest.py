from __future__ import annotations

import uuid
from collections.abc import Iterator
from dataclasses import dataclass

import psycopg
import pytest
from fastapi.testclient import TestClient
from pydantic import SecretStr

from backend.app import criar_app
from backend.services.usuarios import definir_senha
from backend.settings import Settings
from tests.db.conftest import esquema, url_app, url_tst  # noqa: F401  (fixtures reutilizadas)

pytestmark = pytest.mark.banco

BASE = "http://127.0.0.1:8080"
ORIGEM = {"Origin": BASE}
SENHA = "senha-de-teste-123"


@dataclass(frozen=True)
class Usuario:
    user_id: int
    login: str
    senha: str = SENHA


def criar_usuario(url_dono: str, prefixo: str) -> Usuario:
    """Cria usuário commitado, pelo mesmo caminho do comando local (dono do banco)."""
    login = f"{prefixo}_{uuid.uuid4().hex[:8]}"
    with psycopg.connect(url_dono) as conn:
        uid = definir_senha(conn, login, SENHA, criar=True)
    return Usuario(uid, login)


def apagar_usuarios(url_dono: str, usuarios: list[Usuario]) -> None:
    ids = [u.user_id for u in usuarios]
    with psycopg.connect(url_dono) as conn:
        for tabela in (
            "sessao",
            "credencial",
            "snapshot_saldo",
            "cartao_fechamento",
            "reserva_parametro",
            "recorrente_vinculo",
            "recorrente",
            "r2_parametro",
            "cartao_vencimento",
            "linha_credito",
            "transacao_versao",
            "pessoa",
            "conta_versao",
        ):
            conn.execute(f"DELETE FROM {tabela} WHERE user_id = ANY(%s)", (ids,))  # noqa: S608
        conn.execute("DELETE FROM usuario WHERE user_id = ANY(%s)", (ids,))


@pytest.fixture
def settings(url_app: str) -> Settings:  # noqa: F811
    return Settings(db_app_url=SecretStr(url_app), login_max_falhas=3)


@pytest.fixture
def client(settings: Settings) -> Iterator[TestClient]:
    with TestClient(criar_app(settings), base_url=BASE) as c:
        yield c


@pytest.fixture
def usuario(esquema: str) -> Iterator[Usuario]:  # noqa: F811
    u = criar_usuario(esquema, "u")
    yield u
    apagar_usuarios(esquema, [u])


def logar(client: TestClient, u: Usuario) -> str:
    """Faz login e devolve o token CSRF."""
    r = client.post("/api/auth/login", json={"login": u.login, "senha": u.senha}, headers=ORIGEM)
    assert r.status_code == 200, r.text
    token: str = r.json()["csrf_token"]
    return token
