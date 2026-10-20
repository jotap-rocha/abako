"""Rastreabilidade (ADR 021): lista invariantes e critérios sem teste.

Estados de cada item (invariante ou critério de aceite):

- coberto: `teste` não vazio e cada referência é `arquivo.py::test_nome` com a função
  existente, nome iniciado por `test_` e sem skip/skipif/xfail; ou `waiver` humano
  (`humano: <motivo ou link>`, só para critério sem teste automático, ex.: CI). Todo waiver
  ativo é listado na saída, no modo padrão e no estrito.
- pendente: sem teste e a `spec` do item ainda NÃO consta em `specs_entregues.yaml`
  (ou é `futura`). É dívida planejada: aviso, não falha, no modo padrão.
- quebrado: sem teste mas a spec JÁ foi entregue; `spec` ausente/inválida; referência de
  teste inválida; waiver mal formado. Sempre falha.

Além dos itens: toda SPEC cujas tasks em `tasks/abako/` (cabeçalho `# SPEC-NNN...`) estão
todas `Status: done` precisa constar em `specs_entregues.yaml`, senão falha. SPEC-001 só
fecha com as 4 tasks 01-04 done e a SPEC-012 com as 5.

`--estrito` (DoD final): qualquer item sem teste, mesmo pendente, falha; sem waiver, saída
vazia = ok. O fechamento de cada SPEC roda `check --com-banco --estrito`. Sem `--estrito`,
só quebrados falham.

Uso: python -m scripts.rastreabilidade [--estrito]
"""

from __future__ import annotations

import argparse
import ast
import re
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml

RAIZ = Path(__file__).resolve().parent.parent
INVARIANTES = RAIZ / "tests" / "contracts" / "invariantes.yaml"
CRITERIOS = RAIZ / "tests" / "contracts" / "criterios.yaml"
ENTREGUES = RAIZ / "tests" / "contracts" / "specs_entregues.yaml"
TASKS = RAIZ / "tasks" / "abako"
RE_SPEC = re.compile(r"^(SPEC-\d{3}|futura)$")
RE_WAIVER = re.compile(r"^humano:\s*\S")
RE_CAB = re.compile(r"^#\s+(SPEC-\d{3})")
RE_STATUS = re.compile(r"^\*\*Status:\*\*\s*(\S.*?)\s*$", re.MULTILINE)
MARCAS_PULO = ("mark.skip", "mark.skipif", "mark.xfail", "pytest.skip", "pytest.xfail")


@dataclass
class Resultado:
    sem_teste: list[str] = field(default_factory=list)
    pendentes: list[str] = field(default_factory=list)
    quebrados: list[str] = field(default_factory=list)
    motivos: dict[str, str] = field(default_factory=dict)
    waivers: dict[str, str] = field(default_factory=dict)


def _carregar(caminho: Path, chave: str) -> list[dict[str, Any]]:
    dados = yaml.safe_load(caminho.read_text(encoding="utf-8")) or {}
    return list(dados.get(chave) or [])


def _pula(no: ast.AST) -> bool:
    texto = ast.unparse(no)
    return any(m in texto for m in MARCAS_PULO)


def _referencia_ok(ref: str, raiz: Path) -> bool:
    arq, _, nome = str(ref).partition("::")
    caminho = raiz / arq
    if not caminho.is_file():
        return False
    if caminho.suffix != ".py":
        return True  # testes não-Python (SQL, TS): só a existência do arquivo é conferida
    alvo = nome.split("::")[-1].split("[")[0]
    if not alvo.startswith("test_"):
        return False
    try:
        arvore = ast.parse(caminho.read_text(encoding="utf-8"))
    except SyntaxError:
        return False
    for no in ast.walk(arvore):
        if (
            isinstance(no, ast.Assign)
            and any(isinstance(x, ast.Name) and x.id == "pytestmark" for x in no.targets)
            and _pula(no.value)
        ):
            return False
    funcoes = [
        n
        for n in ast.walk(arvore)
        if isinstance(n, ast.FunctionDef | ast.AsyncFunctionDef) and n.name == alvo
    ]
    return bool(funcoes) and not any(_pula(d) for f in funcoes for d in f.decorator_list)


def specs_completas(tasks: Path = TASKS) -> set[str]:
    """SPECs cujas tasks (pelo cabeçalho `# SPEC-NNN`) estão todas `Status: done`."""
    status: dict[str, list[bool]] = {}
    for arq in sorted(tasks.glob("[0-9][0-9]-*.md")):
        texto = arq.read_text(encoding="utf-8")
        cab = RE_CAB.search(texto)
        if not cab:
            continue
        st = RE_STATUS.search(texto)
        status.setdefault(cab.group(1), []).append(st is not None and st.group(1) == "done")
    return {s for s, oks in status.items() if all(oks)}


def specs_faltando(tasks: Path = TASKS, entregues: Path = ENTREGUES) -> list[str]:
    """SPECs com todas as tasks done que ainda não constam em `specs_entregues.yaml`."""
    ent = set((yaml.safe_load(entregues.read_text(encoding="utf-8")) or {}).get("entregues") or [])
    return sorted(specs_completas(tasks) - ent)


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
        spec = str(item.get("spec") or "")
        waiver = str(item.get("waiver") or "").strip()
        problemas: list[str] = []
        if not RE_SPEC.match(spec):
            problemas.append(f"spec ausente ou inválida ({spec!r})")
        if "waiver" in item and not RE_WAIVER.match(waiver):
            problemas.append("waiver deve ser 'humano: <motivo ou link>'")
        elif waiver:
            r.waivers[ident] = waiver
        if problemas:
            r.quebrados.append(ident)
            r.motivos[ident] = "; ".join(problemas)
            continue
        if testes:
            ruins = [t for t in testes if not _referencia_ok(str(t), raiz)]
            if ruins:
                r.quebrados.append(ident)
                r.motivos[ident] = f"teste inválido: {', '.join(map(str, ruins))}"
            continue
        if waiver:
            continue
        r.sem_teste.append(ident)
        if spec in ent:
            r.quebrados.append(ident)
            r.motivos[ident] = f"{spec} entregue, mas sem teste"
        else:
            r.pendentes.append(ident)
            r.motivos[ident] = f"pendente de {spec}"
    return r


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawTextHelpFormatter)
    p.add_argument("--estrito", action="store_true", help="falha com qualquer item sem teste")
    p.add_argument("--invariantes", type=Path, default=INVARIANTES)
    p.add_argument("--criterios", type=Path, default=CRITERIOS)
    p.add_argument("--entregues", type=Path, default=ENTREGUES)
    p.add_argument("--raiz", type=Path, default=RAIZ)
    p.add_argument("--tasks", type=Path, default=None, help="pasta das tasks (padrão tasks/abako)")
    a = p.parse_args(argv)
    r = analisar(a.invariantes, a.criterios, a.entregues, a.raiz)
    tasks = a.tasks or (TASKS if a.raiz == RAIZ else a.raiz / "tasks" / "abako")
    faltando = specs_faltando(tasks, a.entregues) if tasks.is_dir() else []

    for ident in r.quebrados:
        print(f"QUEBRADO {ident}: {r.motivos[ident]}")
    for spec in faltando:
        print(f"QUEBRADO {spec}: todas as tasks done, mas ausente de specs_entregues.yaml")
    for ident, texto in r.waivers.items():
        print(f"waiver ativo {ident}: {texto}")
    rotulo = "SEM TESTE" if a.estrito else "aviso (pendente)"
    for ident in r.pendentes:
        print(f"{rotulo} {ident}: {r.motivos[ident]}")
    if r.quebrados or faltando or (a.estrito and r.sem_teste):
        print(
            f"rastreabilidade: FALHOU ({len(r.quebrados) + len(faltando)} quebrados, "
            f"{len(r.sem_teste)} sem teste)",
            file=sys.stderr,
        )
        return 1
    if r.pendentes:
        print(f"rastreabilidade: ok com {len(r.pendentes)} pendentes (use --estrito no DoD final)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
