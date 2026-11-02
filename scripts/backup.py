"""Backup criptografado do banco (ADR 018/032/037): `pg_dump -Fc | age -r <pública>`.

- Alvo padrão `tst`. `prd` só com `ABAKO_CONFIRMA_PRD=sim` no ambiente real do processo
  (nunca do `.env`), pelo mesmo guarda das migrações (`db.alvo.decidir_alvo`).
- O PC guarda só a chave PÚBLICA: `ABAKO_AGE_RECIPIENT` (`age1...`) ou o arquivo
  `ABAKO_AGE_RECIPIENTS_FILE`. Chave privada nunca é lida aqui (e é recusada se aparecer).
- Pasta: `ABAKO_BACKUP_DIR`, absoluta e fora do repositório.
- `pg_dump` roda dentro do contêiner do projeto (`docker exec`, ver `db/conteiner.py`); a
  saída vai por pipe direto ao `age`: o dump em claro nunca toca o disco. O arquivo nasce
  como `.parcial` (já cifrado) e só é renomeado após sucesso.
- Depois aplica a retenção 7 diários + 4 semanais, só nesta pasta e só em arquivos com o
  padrão `abako-<amb>-AAAAMMDD-HHMMSS.dump.age` do mesmo ambiente.

Uso: `python -m scripts.backup [--alvo tst|prd]`. Imprime só nomes de arquivo.
"""

from __future__ import annotations

import argparse
import os
import re
import sys
from collections.abc import Mapping
from datetime import datetime
from pathlib import Path

from db.alvo import AlvoInvalido, carregar_env, decidir_alvo
from db.conteiner import (
    FalhaExterna,
    ambiente_com_senha,
    comando_no_conteiner,
    credencial,
    encadear,
    exigir_binario,
    nome_conteiner,
    pasta_fora_do_repo,
    verificar_conteiner,
)
from db.retencao import FUSO, expirados, nome_backup

VAR_PASTA = "ABAKO_BACKUP_DIR"
VAR_RECIPIENT = "ABAKO_AGE_RECIPIENT"
VAR_RECIPIENTS_FILE = "ABAKO_AGE_RECIPIENTS_FILE"
RE_RECIPIENT = re.compile(r"^age1[02-9ac-hj-np-z]{58}$")
MARCA_PRIVADA = "AGE-SECRET-KEY-"


def argumentos_recipient(environ: Mapping[str, str]) -> list[str]:
    """`-r age1...` ou `-R <arquivo>`; recusa chave privada no lugar da pública."""
    recipient = environ.get(VAR_RECIPIENT, "").strip()
    arquivo = environ.get(VAR_RECIPIENTS_FILE, "").strip()
    if recipient:
        if MARCA_PRIVADA in recipient.upper():
            raise AlvoInvalido(f"{VAR_RECIPIENT} contém chave PRIVADA; use só a pública (age1...)")
        if not RE_RECIPIENT.match(recipient):
            raise AlvoInvalido(f"{VAR_RECIPIENT} não é uma chave pública age (age1...)")
        return ["-r", recipient]
    if arquivo:
        caminho = Path(arquivo)
        if not caminho.is_file():
            raise AlvoInvalido(f"{VAR_RECIPIENTS_FILE} não aponta para um arquivo")
        if MARCA_PRIVADA in caminho.read_text(encoding="utf-8").upper():
            raise AlvoInvalido(
                f"{VAR_RECIPIENTS_FILE} contém chave PRIVADA; no PC fica só a pública"
            )
        return ["-R", str(caminho)]
    raise AlvoInvalido(f"defina {VAR_RECIPIENT} (ou {VAR_RECIPIENTS_FILE}) com a chave pública")


def pasta_backup(environ: Mapping[str, str]) -> Path:
    valor = environ.get(VAR_PASTA, "").strip()
    if not valor:
        raise AlvoInvalido(f"{VAR_PASTA} não definida (pasta fora do repositório)")
    return pasta_fora_do_repo(Path(valor), VAR_PASTA)


def fazer_backup(
    alvo: str, pasta: Path, environ: Mapping[str, str], agora: datetime | None = None
) -> Path:
    """Gera um backup cifrado em `pasta` e devolve o caminho. Valida tudo antes de executar."""
    ambiente, url = decidir_alvo({**environ, "ABAKO_ENV": alvo})
    pasta = pasta_fora_do_repo(pasta, VAR_PASTA)
    recipient = argumentos_recipient(environ)
    age = exigir_binario("age")
    docker = exigir_binario("docker")
    conteiner = nome_conteiner(environ)
    verificar_conteiner(docker, conteiner)
    cred = credencial(url)

    pasta.mkdir(parents=True, exist_ok=True)
    final = pasta / nome_backup(ambiente, agora or datetime.now(FUSO))
    parcial = final.with_name(final.name + ".parcial")
    if final.exists() or parcial.exists():
        raise FalhaExterna(f"{final.name} já existe; aguarde um segundo e repita")
    dump = comando_no_conteiner(docker, conteiner, cred, "pg_dump", ["-Fc"], stdin=False)
    cifra = [age, *recipient, "-o", str(parcial)]
    try:
        encadear(dump, cifra, env_produtor=ambiente_com_senha(cred.senha))
        if not parcial.is_file() or parcial.stat().st_size == 0:
            raise FalhaExterna("age não gerou o arquivo cifrado")
        parcial.replace(final)
    finally:
        if parcial.exists():
            parcial.unlink()  # parcial já é cifrado; remove para não confundir com backup
    return final


def aplicar_retencao(pasta: Path, ambiente: str) -> list[str]:
    """Remove os expirados do `ambiente`, só arquivos regulares diretamente em `pasta`.

    Revalida a pasta aqui (defesa em profundidade): nunca apaga dentro do repositório.
    """
    pasta = pasta_fora_do_repo(pasta, VAR_PASTA)
    candidatos = [a.name for a in pasta.iterdir() if a.is_file() and not a.is_symlink()]
    removidos: list[str] = []
    for nome in expirados(candidatos, ambiente):
        bruto = pasta / nome
        arq = bruto.resolve()  # symlink é checado antes do resolve, que o seguiria
        if bruto.is_symlink() or arq.parent != pasta or not arq.is_file():
            continue
        arq.unlink()
        removidos.append(nome)
    return removidos


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description="Backup cifrado com age (padrão: tst).")
    p.add_argument("--alvo", choices=["tst", "prd"], default="tst")
    a = p.parse_args(argv)
    carregar_env()
    environ = dict(os.environ)
    try:
        pasta = pasta_backup(environ)
        final = fazer_backup(a.alvo, pasta, environ)
        removidos = aplicar_retencao(pasta, a.alvo)
    except (AlvoInvalido, FalhaExterna) as exc:
        print(f"backup RECUSADO/FALHOU: {exc}", file=sys.stderr)
        return 2
    print(f"backup: {final.name}")
    for nome in removidos:
        print(f"retenção: removido {nome}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
