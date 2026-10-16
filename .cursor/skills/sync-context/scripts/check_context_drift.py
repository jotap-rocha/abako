#!/usr/bin/env python3
"""Detecta drift entre os arquivos de contexto e o estado real do repositório.

Responsabilidade única: comparar o que está declarado em CLAUDE.md/CONTEXT.md com o que existe
no código, e reportar. Este script nunca escreve nos arquivos de contexto.

Dois papéis distintos, para o relatório ser sinal e não ruído:

- `DeclarationSource` — fonte cujos itens o contexto **deve** declarar (dependências, serviços).
  Item ausente do contexto é drift.
- `ContextProbe` — fato que **enriquece** o relatório sem ser drift por si (atividade no git).

Fontes `adaptive` (ex.: variáveis de ambiente) só acusam drift se o contexto já enumera pelo
menos uma delas: se o projeto não rastreia variáveis no CLAUDE.md, cobrar todas viraria ruído.

Segurança: só lê `.env.example` (nunca `.env`) e reporta apenas *nomes* de variáveis — nenhum
valor de secret entra no output.

Uso:
    check_context_drift.py --warn    # imprime relatório legível, exit 0 sempre (padrão)
    check_context_drift.py --check   # exit 1 se houver drift (para gate)
    check_context_drift.py --json    # relatório estruturado em JSON, exit 0
"""

from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
import tomllib
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from pathlib import Path

# Ausência é drift: CLAUDE.md e CONTEXT.md são o contexto; AGENTS.md é o espelho portátil.
REQUIRED_CONTEXT_FILES = ("CLAUDE.md", "AGENTS.md", "CONTEXT.md")
# Ausência é só uma nota: handoff é por sessão, não todo repo tem.
OPTIONAL_CONTEXT_FILES = ("HANDOFF.md",)

# Ferramentas de lint/teste/build que ninguém declara em CLAUDE.md — cobrar viraria ruído.
DEPENDENCY_NOISE = frozenset(
    {
        "black",
        "eslint",
        "flake8",
        "isort",
        "jest",
        "mypy",
        "pip",
        "pre-commit",
        "prettier",
        "pytest",
        "pytest-asyncio",
        "pytest-cov",
        "ruff",
        "setuptools",
        "typescript",
        "types-pyyaml",
        "types-requests",
        "uv",
        "vitest",
        "wheel",
    }
)


@dataclass
class Finding:
    """Um sinal de drift: algo que existe no repositório e não está declarado no contexto."""

    kind: str
    item: str
    evidence: str

    def as_dict(self) -> dict[str, str]:
        return {"kind": self.kind, "item": self.item, "evidence": self.evidence}


@dataclass
class DriftReport:
    findings: list[Finding] = field(default_factory=list)
    notes: list[str] = field(default_factory=list)
    missing_context_files: list[str] = field(default_factory=list)

    @property
    def has_drift(self) -> bool:
        return bool(self.findings) or bool(self.missing_context_files)

    def as_dict(self) -> dict[str, object]:
        return {
            "has_drift": self.has_drift,
            "findings": [f.as_dict() for f in self.findings],
            "notes": self.notes,
            "missing_context_files": self.missing_context_files,
        }


class ContextProbe(ABC):
    """Fato sobre o repositório que enriquece o relatório sem, por si, ser drift."""

    def __init__(self, root: Path) -> None:
        self.root = root

    @abstractmethod
    def notes(self) -> list[str]:
        """Observações para o relatório."""

    def _read(self, rel: str) -> str | None:
        path = self.root / rel
        if not path.is_file():
            return None
        try:
            return path.read_text(encoding="utf-8")
        except OSError:
            return None


class DeclarationSource(ContextProbe):
    """Fonte cujos itens o contexto deve declarar — item ausente é drift."""

    kind: str
    #: Rótulo no plural, usado nas notas agregadas.
    kind_plural: str
    #: Só cobra declaração se o contexto já enumera pelo menos um item desta fonte.
    adaptive: bool = False

    @abstractmethod
    def collect(self) -> set[str]:
        """Itens que o contexto deveria declarar."""

    def notes(self) -> list[str]:
        return []


class DependencySource(DeclarationSource):
    """Dependências declaradas nos manifests de pacote."""

    kind = "dependência"
    kind_plural = "dependências"

    def collect(self) -> set[str]:
        return self._from_requirements() | self._from_pyproject() | self._from_package_json()

    def _from_requirements(self) -> set[str]:
        text = self._read("requirements.txt")
        if text is None:
            return set()
        return {name for line in text.splitlines() if (name := self._package_name(line))}

    def _from_pyproject(self) -> set[str]:
        path = self.root / "pyproject.toml"
        if not path.is_file():
            return set()
        try:
            data = tomllib.loads(path.read_text(encoding="utf-8"))
        except (OSError, tomllib.TOMLDecodeError):
            return set()
        project = data.get("project", {})
        specs: list[str] = list(project.get("dependencies") or [])
        for group in (project.get("optional-dependencies") or {}).values():
            specs.extend(group or [])
        return {name for spec in specs if (name := self._package_name(spec))}

    def _from_package_json(self) -> set[str]:
        text = self._read("package.json")
        if text is None:
            return set()
        try:
            data = json.loads(text)
        except json.JSONDecodeError:
            return set()
        raw: set[str] = set()
        for key in ("dependencies", "devDependencies"):
            raw.update((data.get(key) or {}).keys())
        return {name for item in raw if (name := self._normalize(item))}

    def _package_name(self, spec: str) -> str | None:
        spec = spec.split("#", 1)[0].strip()
        if not spec or spec.startswith("-"):
            return None
        return self._normalize(re.split(r"[\[<>=!~;\s]", spec, maxsplit=1)[0])

    def _normalize(self, name: str) -> str | None:
        name = name.strip().lower()
        if not name or name in DEPENDENCY_NOISE:
            return None
        return name


class ServiceSource(DeclarationSource):
    """Serviços declarados no docker-compose."""

    kind = "serviço"
    kind_plural = "serviços"

    COMPOSE_FILES = ("docker-compose.yml", "docker-compose.yaml", "compose.yml", "compose.yaml")

    def collect(self) -> set[str]:
        for candidate in self.COMPOSE_FILES:
            text = self._read(candidate)
            if text is not None:
                return self._parse_service_names(text)
        return set()

    def _parse_service_names(self, text: str) -> set[str]:
        """Extrai as chaves de primeiro nível sob `services:` sem depender de PyYAML."""
        names: set[str] = set()
        inside = False
        block_indent = 0
        for raw in text.splitlines():
            if not raw.strip() or raw.lstrip().startswith("#"):
                continue
            stripped = raw.strip()
            indent = len(raw) - len(raw.lstrip())
            if not inside:
                if stripped == "services:":
                    inside = True
                    block_indent = indent
                continue
            if indent <= block_indent:
                break
            if indent == block_indent + 2 and stripped.endswith(":"):
                names.add(stripped[:-1].strip().strip("\"'").lower())
        return names


class EnvVarSource(DeclarationSource):
    """Nomes de variáveis de ambiente do .env.example — nunca do .env."""

    kind = "variável de ambiente"
    kind_plural = "variáveis de ambiente"
    adaptive = True

    def collect(self) -> set[str]:
        text = self._read(".env.example")
        if text is None:
            return set()
        names: set[str] = set()
        for line in text.splitlines():
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            name = line.split("=", 1)[0].removeprefix("export ").strip()
            if re.fullmatch(r"[A-Z][A-Z0-9_]*", name):
                names.add(name)
        return names

    def notes(self) -> list[str]:
        if (self.root / ".env").is_file():
            return ["`.env` presente e ignorado por design — só `.env.example` é lido."]
        return []


class GitActivityProbe(ContextProbe):
    """Commits desde a última alteração do CLAUDE.md — sinal de contexto envelhecido."""

    def notes(self) -> list[str]:
        claude = self.root / "CLAUDE.md"
        if not claude.is_file():
            return []
        try:
            result = subprocess.run(
                ["git", "log", "--oneline", f"--since=@{int(claude.stat().st_mtime)}"],
                cwd=self.root,
                capture_output=True,
                text=True,
                timeout=10,
                check=False,
            )
        except (OSError, subprocess.SubprocessError):
            return []
        if result.returncode != 0:
            return []
        count = sum(1 for line in result.stdout.splitlines() if line.strip())
        if count == 0:
            return []
        return [f"{count} commit(s) desde a última alteração do CLAUDE.md."]


class DriftDetector:
    """Compara os fatos coletados com o que o contexto declara."""

    def __init__(
        self,
        root: Path,
        sources: list[DeclarationSource],
        probes: list[ContextProbe],
    ) -> None:
        self.root = root
        self.sources = sources
        self.probes = probes

    def run(self) -> DriftReport:
        report = DriftReport(missing_context_files=self._missing_required_files())
        report.notes.extend(self._optional_file_notes())
        declared = self._declared_text()

        for source in self.sources:
            report.notes.extend(source.notes())
            self._evaluate(source, declared, report)

        for probe in self.probes:
            report.notes.extend(probe.notes())

        return report

    def _evaluate(self, source: DeclarationSource, declared: str, report: DriftReport) -> None:
        items = sorted(source.collect())
        if not items:
            return
        undeclared = [item for item in items if not self._is_declared(item, declared)]
        if not undeclared:
            return
        if source.adaptive and len(undeclared) == len(items):
            report.notes.append(
                f"{len(items)} {source.kind_plural} detectadas, nenhuma citada no contexto — "
                f"este projeto não as rastreia no CLAUDE.md, então ficam fora do sync."
            )
            return
        report.findings.extend(
            Finding(
                kind=source.kind,
                item=item,
                evidence="não mencionado em CLAUDE.md nem CONTEXT.md",
            )
            for item in undeclared
        )

    def _missing_required_files(self) -> list[str]:
        return [name for name in REQUIRED_CONTEXT_FILES if not (self.root / name).is_file()]

    def _optional_file_notes(self) -> list[str]:
        missing = [name for name in OPTIONAL_CONTEXT_FILES if not (self.root / name).is_file()]
        if not missing:
            return []
        return [f"ausente (opcional): {', '.join(missing)}"]

    def _declared_text(self) -> str:
        parts: list[str] = []
        for name in ("CLAUDE.md", "CONTEXT.md"):
            path = self.root / name
            if not path.is_file():
                continue
            try:
                parts.append(path.read_text(encoding="utf-8"))
            except OSError:
                continue
        return "\n".join(parts).lower()

    def _is_declared(self, item: str, declared: str) -> bool:
        if not declared:
            return False
        needle = item.lower()
        if needle in declared:
            return True
        # `fastapi-users` conta como declarado se o texto cita `fastapi_users` ou `fastapi users`.
        loose = re.sub(r"[-_]", "[-_ ]?", re.escape(needle))
        return re.search(loose, declared) is not None


def build_detector(root: Path) -> DriftDetector:
    sources: list[DeclarationSource] = [
        DependencySource(root),
        ServiceSource(root),
        EnvVarSource(root),
    ]
    probes: list[ContextProbe] = [GitActivityProbe(root)]
    return DriftDetector(root, sources, probes)


def format_report(report: DriftReport) -> str:
    lines: list[str] = []

    if not report.has_drift:
        lines.append("Contexto em sync — nenhum drift detectado.")
        lines.extend(f"  nota: {note}" for note in report.notes)
        return "\n".join(lines)

    lines.extend(("Relatório de drift de contexto", ""))

    if report.missing_context_files:
        lines.append("Arquivos de contexto obrigatórios ausentes:")
        lines.extend(f"  - {name}" for name in report.missing_context_files)
        lines.append("")

    by_kind: dict[str, list[Finding]] = {}
    for finding in report.findings:
        by_kind.setdefault(finding.kind, []).append(finding)

    for kind, findings in by_kind.items():
        lines.append(f"Não declarado no contexto ({kind}):")
        lines.extend(f"  - {f.item}" for f in findings)
        lines.append("")

    lines.extend(f"nota: {note}" for note in report.notes)
    lines.extend(("", "Rode /sync-context para revisar e aplicar (relatório antes da edição)."))
    return "\n".join(lines)


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Detecta drift entre os arquivos de contexto e o repositório real.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--warn", action="store_true", help="imprime o relatório e sai com 0 (padrão)")
    mode.add_argument("--check", action="store_true", help="sai com 1 se houver drift")
    mode.add_argument("--json", action="store_true", help="relatório estruturado em JSON")
    parser.add_argument(
        "--root",
        type=Path,
        default=Path.cwd(),
        help="raiz do repositório (padrão: diretório atual)",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    report = build_detector(args.root.resolve()).run()

    if args.json:
        print(json.dumps(report.as_dict(), ensure_ascii=False, indent=2))
        return 0

    print(format_report(report))
    return 1 if (args.check and report.has_drift) else 0


if __name__ == "__main__":
    sys.exit(main())
