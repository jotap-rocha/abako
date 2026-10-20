"""Rastreabilidade (ADR 021): lista invariantes e critérios sem teste.

Regra de três estados, por item (invariante ou critério de aceite):

- coberto: `teste` não vazio e cada referência existe (arquivo e, se `arq::nome`, a função);
  ou `waiver` humano preenchido (só para critério sem teste automático, ex.: CI).
- pendente: sem teste e a `spec` do item ainda NÃO consta em `specs_entregues.yaml`
  (ou é `futura`). É dívida planejada: aviso, não falha, no modo padrão.
- quebrado: sem teste mas a spec JÁ foi entregue, ou referência de teste inexistente.
  Sempre falha.

`--estrito` (DoD final): qualquer item sem teste, mesmo pendente, falha; saída vazia = ok.
Sem `--estrito`: só quebrados falham. `specs_entregues.yaml` é editado ao fechar cada SPEC.

Uso: python -m scripts.rastreabilidade [--estrito]
"""

from __future__ import annotations

import argparse
import ast
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml

RAIZ = Path(__file__).resolve().parent.parent
INVARIANTES = RAIZ / "tests" / "contracts" / "invariantes.yaml"
CRITERIOS = RAIZ / "tests" / "contracts" / "criterios.yaml"
ENTREGUES = RAIZ / "tests" / "contracts" / "specs_entregues.yaml"


@dataclass
class Resultado:
    sem_teste: list[str] = field(default_factory=list)
    pendentes: list[str] = field(default_factory=list)
    quebrados: list[str] = field(default_factory=list)
    motivos: dict[str, str] = field(default_factory=dict)


def _carregar(caminho: Path, chave: str) -> list[dict[str, Any]]:
    dados = yaml.safe_load(caminho.read_text(encoding="utf-8")) or {}
    return list(dados.get(chave) or [])


def _referencia_ok(ref: str, raiz: Path) -> bool:
    arq, _, nome = str(ref).partition("::")
    caminho = raiz / arq
    if not caminho.is_file():
        return False
    if not nome:
        return True
    if caminho.suffix != ".py":
        return True  # testes não-Python (SQL, TS): só a existência do arquivo é conferida
    alvo = nome.split("::")[-1].split("[")[0]
    try:
        arvore = ast.parse(caminho.read_text(encoding="utf-8"))
    except SyntaxError:
        return False
    return any(
        isinstance(n, ast.FunctionDef | ast.AsyncFunctionDef) and n.name == alvo
        for n in ast.walk(arvore)
    )


def analisar(
    invariantes: Path = INVARIANTES,
    criterios: Path = CRITERIOS,
    entregues: Path = ENTREGUES,
    raiz: Path = RAIZ,
) -> Resultado:
    ent = set((yaml.safe_load(entregues.read_text(encoding="utf-8")) or {}).get("entregues") or [])
    itens = _carregar(invariantes, "invariantes") + _carregar(criterios, "criterios")
    r = Resultado()
    for item in itens:
        ident = str(item["id"])
        testes = list(item.get("teste") or [])
        if testes:
            ruins = [t for t in testes if not _referencia_ok(str(t), raiz)]
            if ruins:
                r.quebrados.append(ident)
                r.motivos[ident] = f"teste inexistente: {', '.join(map(str, ruins))}"
            continue
        if str(item.get("waiver") or "").strip():
            continue
        r.sem_teste.append(ident)
        if str(item.get("spec")) in ent:
            r.quebrados.append(ident)
            r.motivos[ident] = f"{item.get('spec')} entregue, mas sem teste"
        else:
            r.pendentes.append(ident)
            r.motivos[ident] = f"pendente de {item.get('spec')}"
    return r


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawTextHelpFormatter)
    p.add_argument("--estrito", action="store_true", help="falha com qualquer item sem teste")
    p.add_argument("--invariantes", type=Path, default=INVARIANTES)
    p.add_argument("--criterios", type=Path, default=CRITERIOS)
    p.add_argument("--entregues", type=Path, default=ENTREGUES)
    p.add_argument("--raiz", type=Path, default=RAIZ)
    a = p.parse_args(argv)
    r = analisar(a.invariantes, a.criterios, a.entregues, a.raiz)

    for ident in r.quebrados:
        print(f"QUEBRADO {ident}: {r.motivos[ident]}")
    rotulo = "SEM TESTE" if a.estrito else "aviso (pendente)"
    for ident in r.pendentes:
        print(f"{rotulo} {ident}: {r.motivos[ident]}")
    if r.quebrados or (a.estrito and r.sem_teste):
        print(
            f"rastreabilidade: FALHOU ({len(r.quebrados)} quebrados, {len(r.sem_teste)} sem teste)",
            file=sys.stderr,
        )
        return 1
    if r.pendentes:
        print(f"rastreabilidade: ok com {len(r.pendentes)} pendentes (use --estrito no DoD final)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
