"""Varredura conservadora de arquivos de texto do projeto-alvo."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

SKIP_DIR_NAMES = frozenset(
    {
        ".git",
        ".hg",
        ".svn",
        ".venv",
        "venv",
        "__pycache__",
        ".mypy_cache",
        ".pytest_cache",
        ".ruff_cache",
        ".harness",
        "node_modules",
        "dist",
        "build",
        ".tox",
    }
)

TEXT_SUFFIXES = frozenset(
    {
        ".py",
        ".sql",
        ".yaml",
        ".yml",
        ".json",
        ".toml",
        ".ini",
        ".cfg",
        ".conf",
        ".txt",
        ".md",
    }
)

TEXT_BASENAMES = frozenset(
    {
        "OWNER",
        "CODEOWNERS",
        "Dockerfile",
        "Makefile",
        "requirements.txt",
        "pyproject.toml",
        ".env.example",
    }
)


@dataclass(frozen=True, slots=True)
class TextFile:
    """Arquivo de texto indexado relativo à raiz do projeto."""

    path: Path
    relative: str
    text: str


def iter_text_files(project_root: Path) -> tuple[TextFile, ...]:
    """Lista arquivos de texto relevantes sob a raiz, de forma determinística."""
    files: list[TextFile] = []
    for path in sorted(project_root.rglob("*")):
        if not path.is_file():
            continue
        if any(part in SKIP_DIR_NAMES for part in path.parts):
            continue
        if not _is_text_candidate(path):
            continue
        try:
            text = path.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError):
            continue
        relative = path.relative_to(project_root).as_posix()
        files.append(TextFile(path=path, relative=relative, text=text))
    return tuple(files)


def _is_text_candidate(path: Path) -> bool:
    if path.name in TEXT_BASENAMES:
        return True
    suffix = path.suffix.lower()
    if suffix in TEXT_SUFFIXES:
        return True
    # arquivos sem extensão como OWNER já cobertos; .env real não é lido de propósito
    return False
