"""SPEC-001-AC-2: o Postgres escuta só em 127.0.0.1:5433."""

from __future__ import annotations

import socket
from pathlib import Path
from typing import Any

import yaml

RAIZ = Path(__file__).resolve().parents[2]
COMPOSE = RAIZ / "docker-compose.yml"
PORTA = 5433


def _compose() -> dict[str, Any]:
    dados = yaml.safe_load(COMPOSE.read_text(encoding="utf-8"))
    assert isinstance(dados, dict)
    return dados


def test_compose_publica_somente_em_loopback() -> None:
    portas = _compose()["services"]["postgres"]["ports"]
    assert portas, "o serviço deve publicar a porta"
    for p in portas:
        assert str(p).startswith("127.0.0.1:"), f"porta exposta fora de loopback: {p}"
        assert "5432:5432" not in str(p).replace("${ABAKO_PG_PORT:-5433}", "")


def test_compose_nomes_vem_de_compose_project_name() -> None:
    dados = _compose()
    nomes = [
        str(dados["name"]),
        str(dados["services"]["postgres"]["container_name"]),
        str(dados["volumes"]["pgdata"]["name"]),
    ]
    for nome in nomes:
        assert "${COMPOSE_PROJECT_NAME" in nome, f"nome fixo no compose: {nome}"


def test_compose_sem_senha_de_admin_literal() -> None:
    texto = COMPOSE.read_text(encoding="utf-8")
    assert "POSTGRES_PASSWORD:" not in texto  # só via arquivo de segredo
    assert "POSTGRES_PASSWORD_FILE" in texto


def _ips_nao_loopback() -> list[str]:
    ips: set[str] = set()
    for info in socket.getaddrinfo(socket.gethostname(), None, socket.AF_INET):
        ip = str(info[4][0])
        if not ip.startswith("127."):
            ips.add(ip)
    return sorted(ips)


def _conecta(host: str) -> bool:
    try:
        with socket.create_connection((host, PORTA), timeout=2):
            return True
    except OSError:
        return False


def test_escuta_apenas_localhost() -> None:
    assert _conecta("127.0.0.1"), (
        "Postgres do abako não responde em 127.0.0.1:5433 (suba o compose)"
    )
    for ip in _ips_nao_loopback():
        assert not _conecta(ip), f"Postgres acessível por {ip}:{PORTA}, deveria ser só loopback"
