r"""Comando único `check` (ADR 021): lint, tipos, testes, contratos e rastreabilidade.

Uso (na raiz do repositório, chamando o python do venv):

    .venv\Scripts\python.exe -m scripts.check              # banco: automático
    .venv\Scripts\python.exe -m scripts.check --com-banco  # exige o `tst` no ar (CI, DoD)
    .venv\Scripts\python.exe -m scripts.check --sem-banco  # pula os testes de banco
    .venv\Scripts\python.exe -m scripts.check --estrito    # rastreabilidade estrita (DoD final)

Todas as etapas rodam; o exit code é 1 se qualquer uma falhar. Testes de banco (marcador
`banco`) usam o `tst` real, nunca mock: no modo automático rodam se 127.0.0.1:5433 responder
(senão, aviso explícito); com `--com-banco`, banco fora do ar é falha. Nunca toca `prd`.
"""

from __future__ import annotations

import argparse
import socket
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
PORTA_BANCO = 5433


@dataclass
class Etapa:
    nome: str
    cmd: list[str]


def banco_no_ar() -> bool:
    try:
        with socket.create_connection(("127.0.0.1", PORTA_BANCO), timeout=2):
            return True
    except OSError:
        return False


def etapas_padrao(banco: str = "nao", estrito: bool = False) -> list[Etapa]:
    """`banco`: 'sim' inclui os testes de banco, 'nao' omite."""
    py = sys.executable
    etapas = [
        Etapa("ruff", [py, "-m", "ruff", "check", "."]),
        Etapa("mypy", [py, "-m", "mypy"]),
        Etapa("pytest (sem banco)", [py, "-m", "pytest", "-q", "-m", "not banco"]),
    ]
    if banco == "sim":
        etapas.append(Etapa("pytest (banco)", [py, "-m", "pytest", "-q", "-m", "banco"]))
    etapas.append(Etapa("contratos", [py, "scripts/validar_contratos.py"]))
    rastro = [py, "-m", "scripts.rastreabilidade"]
    if estrito:
        rastro.append("--estrito")
    etapas.append(Etapa("rastreabilidade", rastro))
    return etapas


def executar(etapas: list[Etapa]) -> int:
    resultados: list[tuple[str, bool]] = []
    for e in etapas:
        print(f"\n=== {e.nome} ===", flush=True)
        ok = subprocess.run(e.cmd, cwd=RAIZ, check=False).returncode == 0
        resultados.append((e.nome, ok))
    print("\n=== resumo ===")
    for nome, ok in resultados:
        print(f"{'ok     ' if ok else 'FALHOU '} {nome}")
    falhou = any(not ok for _, ok in resultados)
    print("check: FALHOU" if falhou else "check: verde")
    return 1 if falhou else 0


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description="Lint, tipos, testes e rastreabilidade do projeto.")
    g = p.add_mutually_exclusive_group()
    g.add_argument("--com-banco", action="store_true", help="exige o tst no ar; senão, falha")
    g.add_argument("--sem-banco", action="store_true", help="não roda os testes de banco")
    p.add_argument("--estrito", action="store_true", help="rastreabilidade estrita (DoD final)")
    p.add_argument("--so-pre-requisitos", action="store_true", help=argparse.SUPPRESS)
    a = p.parse_args(argv)

    if a.sem_banco:
        banco = "nao"
        print("AVISO: testes de banco pulados (--sem-banco).")
    elif banco_no_ar():
        banco = "sim"
    elif a.com_banco:
        print(
            f"FALHOU: --com-banco, mas o banco tst não responde em 127.0.0.1:{PORTA_BANCO} "
            "(suba o contêiner: docker compose up -d)."
        )
        return 1
    else:
        banco = "nao"
        print(
            f"AVISO: banco fora do ar em 127.0.0.1:{PORTA_BANCO}; testes de banco NÃO rodaram "
            "(use --com-banco para exigir)."
        )
    if a.so_pre_requisitos:
        return 0
    return executar(etapas_padrao(banco, a.estrito))


if __name__ == "__main__":
    raise SystemExit(main())
