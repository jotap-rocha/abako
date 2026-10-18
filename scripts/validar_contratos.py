"""Valida a consistência dos contratos de teste (ADR 021).

Confere IDs únicos e referências cruzadas entre invariantes, fixtures e critérios.
Não exige que `teste` esteja preenchido: isso é o script de rastreabilidade (SPEC-001).
Uso: python scripts/validar_contratos.py
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

import yaml

RAIZ = Path(__file__).resolve().parent.parent
INVARIANTES = RAIZ / "tests" / "contracts" / "invariantes.yaml"
CRITERIOS = RAIZ / "tests" / "contracts" / "criterios.yaml"
FIXTURES = RAIZ / "fixtures" / "numericos.yaml"

RE_INV = re.compile(r"^INV-\d{2}$")
RE_FIX = re.compile(r"^F-[A-Z0-9]+-\d{2}$")
RE_AC = re.compile(r"^SPEC-\d{3}-AC-\d+$")
RE_SPEC = re.compile(r"^(SPEC-\d{3}|futura)$")


def carregar(caminho: Path) -> dict:
    with caminho.open(encoding="utf-8") as f:
        dados = yaml.safe_load(f)
    if not isinstance(dados, dict):
        raise SystemExit(f"{caminho}: raiz deve ser um mapeamento")
    return dados


def ids_unicos(itens: list[dict], rotulo: str, padrao: re.Pattern[str], erros: list[str]) -> set[str]:
    vistos: set[str] = set()
    for item in itens:
        ident = str(item.get("id", ""))
        if not padrao.match(ident):
            erros.append(f"{rotulo}: id inválido {ident!r}")
        if ident in vistos:
            erros.append(f"{rotulo}: id duplicado {ident}")
        vistos.add(ident)
    return vistos


def main() -> int:
    erros: list[str] = []
    invs = carregar(INVARIANTES).get("invariantes") or []
    fixs = carregar(FIXTURES).get("fixtures") or []
    crits = carregar(CRITERIOS).get("criterios") or []

    ids_inv = ids_unicos(invs, "invariantes", RE_INV, erros)
    ids_fix = ids_unicos(fixs, "fixtures", RE_FIX, erros)
    ids_ac = ids_unicos(crits, "criterios", RE_AC, erros)

    for inv in invs:
        if not str(inv.get("enunciado", "")).strip():
            erros.append(f"{inv.get('id')}: enunciado vazio")
        if not RE_SPEC.match(str(inv.get("spec", ""))):
            erros.append(f"{inv.get('id')}: spec inválida {inv.get('spec')!r}")
        for f in inv.get("fixtures") or []:
            if f not in ids_fix:
                erros.append(f"{inv.get('id')}: fixture inexistente {f}")

    for fix in fixs:
        for i in fix.get("invariantes") or []:
            if i not in ids_inv:
                erros.append(f"{fix.get('id')}: invariante inexistente {i}")

    for ac in crits:
        for i in ac.get("invariantes") or []:
            if i not in ids_inv:
                erros.append(f"{ac.get('id')}: invariante inexistente {i}")
        for f in ac.get("fixtures") or []:
            if f not in ids_fix:
                erros.append(f"{ac.get('id')}: fixture inexistente {f}")
        for campo in ("dado", "quando", "entao"):
            if not str(ac.get(campo, "")).strip():
                erros.append(f"{ac.get('id')}: campo {campo!r} vazio")

    # Valores monetários das fixtures devem ser texto decimal, nunca número (INV-14).
    def varrer(no: object, caminho: str) -> None:
        if isinstance(no, float):
            erros.append(f"{caminho}: float em fixture (use string decimal)")
        elif isinstance(no, dict):
            for k, v in no.items():
                varrer(v, f"{caminho}.{k}")
        elif isinstance(no, list):
            for n, v in enumerate(no):
                varrer(v, f"{caminho}[{n}]")

    for fix in fixs:
        varrer(fix, str(fix.get("id")))

    if erros:
        print("Contratos inconsistentes:", file=sys.stderr)
        for e in erros:
            print(f"  - {e}", file=sys.stderr)
        return 1
    print(f"ok: {len(ids_inv)} invariantes, {len(ids_fix)} fixtures, {len(ids_ac)} critérios")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
