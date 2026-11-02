"""Execução de `pg_dump`/`pg_restore` dentro do contêiner do projeto e encadeamento com `age`.

Por que `docker exec`: o cliente do Postgres no contêiner tem a mesma versão do servidor
(17.6), funciona igual no Windows do usuário (sem instalar cliente) e no CI (serviço do job,
id em `ABAKO_PG_CONTAINER`). A senha vai por `PGPASSWORD` no ambiente do processo e
`docker exec -e PGPASSWORD` (sem valor), então nunca aparece na linha de comando.

O dump trafega só por pipe entre os processos: nunca é escrito em claro no disco.
"""

from __future__ import annotations

import os
import re
import shutil
import subprocess
import threading
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import IO
from urllib.parse import unquote, urlsplit

from db.alvo import PORTA_ABAKO, RAIZ, AlvoInvalido

VAR_CONTEINER = "ABAKO_PG_CONTAINER"
PORTA_INTERNA = 5432  # porta do Postgres dentro do contêiner (publicada em 127.0.0.1:5433)
RE_CONTEINER = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.-]*$")
DICA_AGE = (
    "binário `age` não encontrado no PATH. Instale: `winget install FiloSottile.age` "
    "(Windows) ou `apt-get install age` (Ubuntu) e abra um terminal novo."
)


class FalhaExterna(Exception):
    """Um processo externo (docker, pg_dump, pg_restore, age) falhou."""


@dataclass(frozen=True)
class Credencial:
    usuario: str
    senha: str
    banco: str


def credencial(url: str) -> Credencial:
    """Usuário, senha e banco de uma URL já validada pelo guarda de alvo."""
    p = urlsplit(url)
    if not p.username or p.password is None:
        raise AlvoInvalido("URL do banco sem usuário ou senha")
    return Credencial(unquote(p.username), unquote(p.password), p.path.lstrip("/"))


def exigir_binario(nome: str) -> str:
    caminho = shutil.which(nome)
    if not caminho:
        if nome.startswith("age"):
            raise FalhaExterna(DICA_AGE.replace("`age`", f"`{nome}`"))
        raise FalhaExterna(f"binário `{nome}` não encontrado no PATH")
    return caminho


def nome_conteiner(environ: Mapping[str, str]) -> str:
    """`ABAKO_PG_CONTAINER` (CI) ou `<COMPOSE_PROJECT_NAME>-postgres` (local)."""
    nome = environ.get(VAR_CONTEINER) or (
        f"{environ['COMPOSE_PROJECT_NAME']}-postgres" if environ.get("COMPOSE_PROJECT_NAME") else ""
    )
    if not nome:
        raise AlvoInvalido(
            f"defina COMPOSE_PROJECT_NAME (ou {VAR_CONTEINER}) para achar o contêiner"
        )
    if not RE_CONTEINER.match(nome):
        raise AlvoInvalido(f"nome de contêiner inválido: {nome!r}")
    return nome


def publicacao_exata(saida_docker_port: str) -> bool:
    """A porta interna está publicada SÓ em 127.0.0.1:5433 (nada de 0.0.0.0 ou [::])."""
    publicado = {linha.strip() for linha in saida_docker_port.splitlines() if linha.strip()}
    return publicado == {f"127.0.0.1:{PORTA_ABAKO}"}


def verificar_conteiner(docker: str, nome: str) -> None:
    """O contêiner tem de publicar o Postgres só em 127.0.0.1:5433 (é o do projeto, ADR 019)."""
    r = subprocess.run(
        [docker, "port", nome, f"{PORTA_INTERNA}/tcp"],
        capture_output=True,
        text=True,
        check=False,
    )
    if r.returncode != 0 or not publicacao_exata(r.stdout):
        raise AlvoInvalido(
            f"contêiner {nome!r} não publica o Postgres exatamente em 127.0.0.1:{PORTA_ABAKO} "
            "(não é o contêiner do projeto, está parado ou expõe outra interface)"
        )


def comando_no_conteiner(
    docker: str, nome: str, cred: Credencial, programa: str, args: Sequence[str], stdin: bool
) -> list[str]:
    base = [docker, "exec"]
    if stdin:
        base.append("-i")
    return [
        *base,
        "-e",
        "PGPASSWORD",
        nome,
        programa,
        "-h",
        "127.0.0.1",
        "-p",
        str(PORTA_INTERNA),
        "-U",
        cred.usuario,
        "-d",
        cred.banco,
        "--no-password",
        *args,
    ]


def ambiente_com_senha(senha: str) -> dict[str, str]:
    env = dict(os.environ)
    env["PGPASSWORD"] = senha
    return env


def pasta_fora_do_repo(caminho: Path, rotulo: str) -> Path:
    """Caminho absoluto resolvido e fora do repositório (backups e chaves nunca no git)."""
    if not caminho.is_absolute():
        raise AlvoInvalido(f"{rotulo} precisa ser caminho absoluto")
    resolvido = caminho.resolve()
    raiz = RAIZ.resolve()
    if resolvido == raiz or raiz in resolvido.parents:
        raise AlvoInvalido(f"{rotulo} não pode ficar dentro do repositório")
    return resolvido


def _drenar(fluxo: IO[bytes] | None, destino: list[bytes]) -> threading.Thread:
    def ler() -> None:
        if fluxo is not None:
            destino.append(fluxo.read())

    t = threading.Thread(target=ler, daemon=True)
    t.start()
    return t


# Linhas de stderr que podem carregar conteúdo de linha (ex.: `CONTEXT: COPY t, line 3,
# column c: "<valor>"`) ou SQL com valores: nunca são repassadas.
MARCAS_PERIGOSAS = ("CONTEXT:", "DETAIL:", "HINT:", "QUERY:", "LINE ", "Command was:", "COPY ")
RE_LITERAL = re.compile(r"\"[^\"]*\"|'[^']*'|\(.*?\)=\(.*?\)")
RE_ERRO = re.compile(r"(?i)\b(error|erro|fatal)\b")


def erro_seguro(stderr: bytes) -> str:
    """Primeira linha de erro do stderr, sem literais e sem linhas que carregam dados.

    Mensagens de `pg_restore`/`pg_dump` podem citar valores de linhas reais; aqui sobra só o
    tipo do erro (literais entre aspas viram `"…"`). Sem linha de erro reconhecível: `-`.
    """
    for bruta in stderr.decode("utf-8", "replace").splitlines():
        linha = bruta.strip()
        if not linha or any(m in linha for m in MARCAS_PERIGOSAS):
            continue
        if RE_ERRO.search(linha):
            return RE_LITERAL.sub('"…"', linha)[:200]
    return "-"


def encadear(
    produtor: Sequence[str],
    consumidor: Sequence[str],
    env_produtor: Mapping[str, str] | None = None,
    env_consumidor: Mapping[str, str] | None = None,
) -> None:
    """Roda `produtor | consumidor` sem arquivo intermediário; falha se qualquer um falhar.

    O stderr de cada lado é lido em thread (evita travar o pipe) e, na exceção, só aparece o
    código de saída e a 1ª linha de erro filtrada por `erro_seguro` (sem valores de linha).
    """
    p1 = subprocess.Popen(
        list(produtor), stdout=subprocess.PIPE, stderr=subprocess.PIPE, env=env_produtor
    )
    try:
        p2 = subprocess.Popen(
            list(consumidor),
            stdin=p1.stdout,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            env=env_consumidor,
        )
    except BaseException:
        p1.kill()  # sem consumidor, o produtor ficaria preso no pipe
        p1.wait()
        raise
    if p1.stdout is not None:
        p1.stdout.close()  # o consumidor é o único leitor; permite SIGPIPE ao produtor
    err1: list[bytes] = []
    err2: list[bytes] = []
    saida2: list[bytes] = []
    threads = [_drenar(p1.stderr, err1), _drenar(p2.stderr, err2), _drenar(p2.stdout, saida2)]
    rc2 = p2.wait()
    rc1 = p1.wait()
    for t in threads:
        t.join()
    if rc1 != 0 or rc2 != 0:
        raise FalhaExterna(
            f"{Path(produtor[0]).name} rc={rc1}: {erro_seguro(b''.join(err1))} | "
            f"{Path(consumidor[0]).name} rc={rc2}: {erro_seguro(b''.join(err2))}"
        )
