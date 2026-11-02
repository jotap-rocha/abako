"""SPEC-001-AC-12: a restauração recusa `prd` (e qualquer alvo fora do descartável) antes de
ler `.env`, chamar processo externo ou conectar. Não precisa de banco.

Arquivo de backup (nome válido) e identidade EXISTEM no tmp_path, para que a recusa só possa
vir do guarda de alvo. O controle positivo (`--alvo restauracao`) passa por essas checagens e
chega ao primeiro efeito (ler `.env`), provando a ordem das garantias."""

from __future__ import annotations

import subprocess
from pathlib import Path
from typing import NoReturn

import psycopg
import pytest

from db.alvo import AlvoInvalido, verificar_alvo_restauracao, verificar_url_restauracao
from scripts import restaurar

MSG_PRD = "restauração em prd é recusada (ADR 032)"


class ChegouAoEfeito(Exception):
    """Algum efeito (ler .env, processo, conexão) foi alcançado."""


def _efeito(*_a: object, **_k: object) -> NoReturn:
    raise ChegouAoEfeito


@pytest.fixture
def sem_efeitos(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(psycopg, "connect", _efeito)
    monkeypatch.setattr(subprocess, "Popen", _efeito)
    monkeypatch.setattr(subprocess, "run", _efeito)
    monkeypatch.setattr(restaurar, "carregar_env", _efeito)


@pytest.fixture
def arquivos(tmp_path: Path) -> list[str]:
    """Backup sintético (só o cabeçalho age, sem conteúdo) e identidade inventada."""
    arq = tmp_path / "abako-tst-20261101-020000.dump.age"
    arq.write_bytes(b"age-encryption.org/v1\n")
    ident = tmp_path / "identidade-teste.txt"
    ident.write_text("# identidade inventada para teste\n", encoding="utf-8")
    return ["--arquivo", str(arq), "--identidade", str(ident)]


@pytest.mark.parametrize(
    ("alvo", "mensagem"),
    [
        ("prd", MSG_PRD),
        ("tst", "alvo de restauração 'tst' recusado: só 'restauracao'"),
        ("postgres", "alvo de restauração 'postgres' recusado: só 'restauracao'"),
        ("PRD", "alvo de restauração 'PRD' recusado: só 'restauracao'"),
        ("", "alvo de restauração '' recusado: só 'restauracao'"),
    ],
)
def test_recusa_alvo_prd(
    alvo: str,
    mensagem: str,
    sem_efeitos: None,
    arquivos: list[str],
    capsys: pytest.CaptureFixture[str],
) -> None:
    rc = restaurar.main(["--alvo", alvo, *arquivos])
    assert rc == 2
    erro = capsys.readouterr().err
    assert "RECUSADA" in erro
    assert mensagem in erro


def test_controle_alvo_descartavel_chega_ao_primeiro_efeito(
    sem_efeitos: None, arquivos: list[str]
) -> None:
    # Mesmos arquivos: com o alvo certo, as checagens passam e o próximo passo é ler o .env.
    with pytest.raises(ChegouAoEfeito):
        restaurar.main(["--alvo", "restauracao", *arquivos])


def test_alvo_descartavel_e_o_unico_aceito() -> None:
    verificar_alvo_restauracao("restauracao")
    with pytest.raises(AlvoInvalido, match="prd é recusada"):
        verificar_alvo_restauracao("prd")


@pytest.mark.parametrize(
    "url",
    [
        "postgresql://abako_owner_restauracao:x@127.0.0.1:5433/prd",
        "postgresql://abako_owner_restauracao:x@127.0.0.1:5433/tst",
        "postgresql://abako_owner_prd:x@127.0.0.1:5433/restauracao",
        "postgresql://abako_owner_restauracao:x@127.0.0.1:5432/restauracao",
        "postgresql://abako_owner_restauracao:x@10.0.0.5:5433/restauracao",
        "postgresql://abako_owner_restauracao:x@127.0.0.1:5433/restauracao?dbname=prd",
        "",
    ],
)
def test_url_do_descartavel_e_conferida(url: str) -> None:
    with pytest.raises(AlvoInvalido):
        verificar_url_restauracao(url)
