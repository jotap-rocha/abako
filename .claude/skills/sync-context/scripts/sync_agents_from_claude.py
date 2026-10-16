#!/usr/bin/env python3
"""Deriva o AGENTS.md a partir do CLAUDE.md — são arquivos irmãos, não cópias divergentes.

O AGENTS.md é o espelho portátil lido por Cursor/Windsurf/Codex: mesmo conteúdo, sem depender
de `.claude/`. Manter os dois à mão garante divergência; este script torna a derivação
determinística.

Transformações aplicadas:

1. Paths de artefato espelhado: `.claude/agents/...` → `.cursor/agents/...`. A reescrita é
   **estrutural**, não textual — só casa `.claude/` seguido de um subdiretório espelhado
   conhecido. Assim `.claude/{agents,skills,...}` (que descreve a própria regra de espelhamento)
   e `.claude/settings.json` (que não existe no Cursor) ficam intactos.
2. Arquivos de rule ganham a extensão do Cursor: `.cursor/rules/backend.md` → `.mdc`. O glob
   `rules/*.md` não é tocado.
3. Seções específicas do Claude Code (hooks, settings, MCP) são removidas.

Conteúdo que só faz sentido no AGENTS.md fica protegido entre `<!-- agents-only:start -->` e
`<!-- agents-only:end -->`: o script preserva esses blocos verbatim. Um bloco cuja primeira
linha é um heading `## X` **substitui** a seção `## X` derivada do CLAUDE.md; blocos com heading
inexistente no CLAUDE.md são anexados ao final, na ordem original.

Uso:
    sync_agents_from_claude.py --check   # exit 1 se o AGENTS.md divergiu do derivado
    sync_agents_from_claude.py --diff    # mostra o diff unificado, exit 0
    sync_agents_from_claude.py --apply   # grava o AGENTS.md derivado
"""

from __future__ import annotations

import argparse
import difflib
import re
import sys
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from pathlib import Path

BLOCK_START = "<!-- agents-only:start -->"
BLOCK_END = "<!-- agents-only:end -->"

PROVENANCE = (
    "<!-- Derivado de CLAUDE.md por .claude/skills/sync-context/scripts/sync_agents_from_claude.py"
    " — edite o CLAUDE.md, ou use blocos agents-only. -->"
)

#: Subdiretórios de `.claude/` que o install-harness espelha em `.cursor/`.
MIRRORED_SUBDIRS = ("agents", "skills", "kb", "commands", "rules", "guias", "dev", "design", "projetos")

#: Seções que não existem fora do Claude Code.
CLAUDE_ONLY_HEADING_TERMS = ("hook", "settings.json", "mcp")

PREAMBLE = "__preamble__"


@dataclass
class Section:
    """Um trecho do documento: heading (ou PREAMBLE) + corpo."""

    heading: str
    lines: list[str] = field(default_factory=list)

    def render(self) -> str:
        body = "\n".join(self.lines).strip("\n")
        if self.heading == PREAMBLE:
            return body
        return f"{self.heading}\n\n{body}" if body else self.heading


class Transformation(ABC):
    """Uma reescrita textual isolada e testável."""

    @abstractmethod
    def apply(self, text: str) -> str: ...


class MirroredPathRewrite(Transformation):
    """`.claude/<subdir espelhado>` → `.cursor/<subdir espelhado>`."""

    def __init__(self, subdirs: tuple[str, ...] = MIRRORED_SUBDIRS) -> None:
        self.pattern = re.compile(rf"\.claude/({'|'.join(subdirs)})\b")

    def apply(self, text: str) -> str:
        return self.pattern.sub(r".cursor/\1", text)


class RuleExtensionRewrite(Transformation):
    """`.cursor/rules/<nome>.md` → `.cursor/rules/<nome>.mdc`, preservando o glob `rules/*.md`."""

    PATTERN = re.compile(r"(\.cursor/rules/[\w.-]+)\.md\b")

    def apply(self, text: str) -> str:
        return self.PATTERN.sub(r"\1.mdc", text)


class MarkdownDocument:
    """Documento markdown fatiado em seções de nível 2."""

    HEADING = re.compile(r"^##\s+\S")

    def __init__(self, sections: list[Section]) -> None:
        self.sections = sections

    @classmethod
    def parse(cls, text: str) -> MarkdownDocument:
        sections = [Section(PREAMBLE)]
        for line in text.splitlines():
            if cls.HEADING.match(line):
                sections.append(Section(line.strip()))
            else:
                sections[-1].lines.append(line)
        return cls(sections)

    def render(self) -> str:
        rendered = [section.render() for section in self.sections if section.render()]
        return "\n\n".join(rendered) + "\n"

    def without_headings_matching(self, terms: tuple[str, ...]) -> MarkdownDocument:
        def is_claude_only(section: Section) -> bool:
            if section.heading == PREAMBLE:
                return False
            lowered = section.heading.lower()
            return any(term in lowered for term in terms)

        return MarkdownDocument([s for s in self.sections if not is_claude_only(s)])

    def transformed(self, transformations: list[Transformation]) -> MarkdownDocument:
        sections: list[Section] = []
        for section in self.sections:
            heading = section.heading
            lines = section.lines
            for transformation in transformations:
                if heading != PREAMBLE:
                    heading = transformation.apply(heading)
                lines = [transformation.apply(line) for line in lines]
            sections.append(Section(heading, lines))
        return MarkdownDocument(sections)


@dataclass
class ProtectedBlock:
    """Bloco `agents-only` extraído do AGENTS.md atual."""

    lines: list[str]

    @property
    def heading(self) -> str | None:
        for line in self.lines:
            stripped = line.strip()
            if stripped:
                return stripped if MarkdownDocument.HEADING.match(stripped) else None
        return None

    def render(self) -> str:
        body = "\n".join(self.lines).strip("\n")
        return f"{BLOCK_START}\n{body}\n{BLOCK_END}"


class ProtectedBlockReader:
    """Extrai os blocos `agents-only` de um AGENTS.md existente."""

    def read(self, text: str | None) -> list[ProtectedBlock]:
        if not text:
            return []
        blocks: list[ProtectedBlock] = []
        current: list[str] | None = None
        for line in text.splitlines():
            marker = line.strip()
            if marker == BLOCK_START:
                current = []
                continue
            if marker == BLOCK_END:
                if current is not None:
                    blocks.append(ProtectedBlock(current))
                current = None
                continue
            if current is not None:
                current.append(line)
        return blocks


class AgentsMirrorBuilder:
    """Monta o AGENTS.md derivado do CLAUDE.md, respeitando os blocos protegidos."""

    def __init__(self, transformations: list[Transformation] | None = None) -> None:
        self.transformations = transformations or [MirroredPathRewrite(), RuleExtensionRewrite()]

    def build(self, claude_text: str, agents_text: str | None) -> str:
        blocks = ProtectedBlockReader().read(agents_text)
        overrides = {b.heading: b for b in blocks if b.heading}
        derived = (
            MarkdownDocument.parse(claude_text)
            .without_headings_matching(CLAUDE_ONLY_HEADING_TERMS)
            .transformed(self.transformations)
        )

        parts: list[str] = []
        used: set[str] = set()
        for section in derived.sections:
            override = overrides.get(section.heading)
            if override is not None:
                parts.append(override.render())
                used.add(section.heading)
                continue
            rendered = section.render()
            if rendered:
                parts.append(self._with_provenance(rendered) if not parts else rendered)

        parts.extend(b.render() for b in blocks if b.heading not in used)
        return "\n\n".join(parts) + "\n"

    def _with_provenance(self, preamble: str) -> str:
        lines = preamble.splitlines()
        title_index = next((i for i, line in enumerate(lines) if line.startswith("# ")), None)
        if title_index is None:
            return f"{PROVENANCE}\n{preamble}"
        lines.insert(title_index + 1, "")
        lines.insert(title_index + 2, PROVENANCE)
        return "\n".join(lines)


def strip_provenance(text: str) -> str:
    """Remove a linha de proveniência para comparar conteúdo, não metadados."""
    return "\n".join(line for line in text.splitlines() if line.strip() != PROVENANCE)


@dataclass
class MirrorResult:
    expected: str
    actual: str | None

    @property
    def in_sync(self) -> bool:
        if self.actual is None:
            return False
        return strip_provenance(self.expected).strip() == strip_provenance(self.actual).strip()

    def diff(self) -> str:
        actual_lines = (self.actual or "").splitlines(keepends=True)
        return "".join(
            difflib.unified_diff(
                actual_lines,
                self.expected.splitlines(keepends=True),
                fromfile="AGENTS.md (atual)",
                tofile="AGENTS.md (derivado do CLAUDE.md)",
            )
        )


def evaluate(root: Path) -> MirrorResult:
    claude_path = root / "CLAUDE.md"
    agents_path = root / "AGENTS.md"
    if not claude_path.is_file():
        raise FileNotFoundError(f"CLAUDE.md não encontrado em {root}")

    claude_text = claude_path.read_text(encoding="utf-8")
    agents_text = agents_path.read_text(encoding="utf-8") if agents_path.is_file() else None
    expected = AgentsMirrorBuilder().build(claude_text, agents_text)
    return MirrorResult(expected=expected, actual=agents_text)


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Deriva o AGENTS.md a partir do CLAUDE.md.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--check", action="store_true", help="sai com 1 se o AGENTS.md divergiu")
    mode.add_argument("--diff", action="store_true", help="mostra o diff sem gravar (padrão)")
    mode.add_argument("--apply", action="store_true", help="grava o AGENTS.md derivado")
    parser.add_argument(
        "--root",
        type=Path,
        default=Path.cwd(),
        help="raiz do repositório (padrão: diretório atual)",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    root = args.root.resolve()

    try:
        result = evaluate(root)
    except (FileNotFoundError, OSError) as exc:
        print(f"erro: {exc}", file=sys.stderr)
        return 2

    if args.apply:
        if result.in_sync:
            print("AGENTS.md já está em sync com o CLAUDE.md — nada a fazer.")
            return 0
        (root / "AGENTS.md").write_text(result.expected, encoding="utf-8")
        print("AGENTS.md regravado a partir do CLAUDE.md.")
        return 0

    if result.in_sync:
        print("AGENTS.md em sync com o CLAUDE.md.")
        return 0

    print(result.diff() or "AGENTS.md ausente — rode --apply para gerá-lo.")
    print("AGENTS.md divergiu do CLAUDE.md. Rode --apply para regravar.")
    return 1 if args.check else 0


if __name__ == "__main__":
    sys.exit(main())
