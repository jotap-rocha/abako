"""SPEC-001-AC-13: o backup é criptografado e não contém `.env` nem segredo.

Faz um backup REAL do `tst` sintético com um par de chaves age EFÊMERO gerado em `tmp_path`
(nenhuma chave do usuário é usada). Se `age`/`age-keygen` não estiverem no PATH, o teste
FALHA com instrução de instalação: um backup não testado não pode passar em silêncio.
A decifragem para conferência é feita só em memória (pipe), nunca em disco.
"""

from __future__ import annotations

import os
import shutil
import subprocess
from pathlib import Path
from urllib.parse import urlsplit

import pytest

from db.conteiner import DICA_AGE
from scripts import backup

CABECALHO_AGE = b"age-encryption.org/v1\n"
# Textos que existem em qualquer dump do esquema base e não podem aparecer cifrados.
TEXTOS_DO_DUMP = [b"PGDMP", b"transacao_versao", b"conta_versao", b"CREATE TABLE", b"usuario"]
VARS_SEGREDO = [
    "ABAKO_OWNER_TST_PASSWORD",
    "ABAKO_OWNER_PRD_PASSWORD",
    "ABAKO_APP_PASSWORD",
    "ABAKO_PIPELINE_PASSWORD",
    "ABAKO_OWNER_RESTAURACAO_PASSWORD",
]
VARS_URL = [
    "ABAKO_DB_MIGRATE_URL_TST",
    "ABAKO_DB_MIGRATE_URL_PRD",
    "ABAKO_DB_APP_URL",
    "ABAKO_DB_PIPELINE_URL",
    "ABAKO_DB_RESTAURACAO_URL",
]


def _exigir(nome: str) -> str:
    caminho = shutil.which(nome)
    if not caminho:
        pytest.fail(DICA_AGE.replace("`age`", f"`{nome}`"))
    return caminho


def _segredos_do_ambiente() -> list[bytes]:
    valores = [os.environ.get(v, "") for v in VARS_SEGREDO]
    valores += [urlsplit(os.environ.get(v, "")).password or "" for v in VARS_URL]
    return [v.encode() for v in valores if len(v) >= 4]


@pytest.mark.banco
def test_backup_criptografado(
    esquema: str, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    age = _exigir("age")
    keygen = _exigir("age-keygen")
    chaves = tmp_path / "chaves"
    chaves.mkdir()
    identidade = chaves / "efemera.txt"
    subprocess.run([keygen, "-o", str(identidade)], check=True, capture_output=True)
    publica = subprocess.run(
        [keygen, "-y", str(identidade)], check=True, capture_output=True, text=True
    ).stdout.strip()
    pasta = tmp_path / "backups"
    monkeypatch.setenv("ABAKO_BACKUP_DIR", str(pasta))
    monkeypatch.setenv("ABAKO_AGE_RECIPIENT", publica)
    monkeypatch.delenv("ABAKO_AGE_RECIPIENTS_FILE", raising=False)

    assert backup.main(["--alvo", "tst"]) == 0

    arquivos = sorted(pasta.iterdir())
    assert len(arquivos) == 1, f"arquivo intermediário no disco: {[a.name for a in arquivos]}"
    arq = arquivos[0]
    assert arq.name.startswith("abako-tst-") and arq.name.endswith(".dump.age")
    cifrado = arq.read_bytes()
    assert cifrado.startswith(CABECALHO_AGE)
    proibidos = [*TEXTOS_DO_DUMP, *_segredos_do_ambiente(), b"ABAKO_", b"COMPOSE_PROJECT_NAME"]
    proibidos.append(b"AGE-SECRET-KEY-")
    for texto in proibidos:
        assert texto not in cifrado, "texto em claro no arquivo cifrado"
    # Só as chaves efêmeras e o backup existem no tmp: nada de dump em claro em lugar nenhum.
    todos = sorted(p.relative_to(tmp_path).as_posix() for p in tmp_path.rglob("*") if p.is_file())
    assert todos == ["backups/" + arq.name, "chaves/efemera.txt"]

    # Conferência: decifrado (em memória) é um dump real do tst e não carrega segredo nem .env.
    claro = subprocess.run(
        [age, "-d", "-i", str(identidade), str(arq)], check=True, capture_output=True
    ).stdout
    assert claro.startswith(b"PGDMP")
    assert b"transacao_versao" in claro
    for texto in [*_segredos_do_ambiente(), b"ABAKO_", b"COMPOSE_PROJECT_NAME", b"PASSWORD"]:
        assert texto not in claro, "segredo/variável de ambiente dentro do dump"


def test_backup_prd_sem_confirmacao_recusa_antes_de_executar(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    def proibido(*_a: object, **_k: object) -> None:
        raise AssertionError("prd sem confirmação não pode chegar a executar processo")

    monkeypatch.delenv("ABAKO_CONFIRMA_PRD", raising=False)
    monkeypatch.setattr(subprocess, "Popen", proibido)
    monkeypatch.setattr(subprocess, "run", proibido)
    monkeypatch.setenv("ABAKO_BACKUP_DIR", str(tmp_path / "b"))
    assert backup.main(["--alvo", "prd"]) == 2
    assert not (tmp_path / "b").exists()
