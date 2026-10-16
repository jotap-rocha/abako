"""Paths relativos da pasta ``fluxo/`` por projeto."""

from __future__ import annotations

from pathlib import Path

from config.fluxo_events.contract import FluxoEventsContract, FluxoPaths


def fluxo_dir_for_slug(projetos_root: Path, slug: str) -> Path:
    """Retorna ``{projetos_root}/{slug}/fluxo``."""
    return Path(projetos_root) / slug / "fluxo"


def events_path(
    projetos_root: Path,
    slug: str,
    *,
    paths: FluxoPaths | None = None,
) -> Path:
    """Path de ``events.jsonl`` sob a pasta fluxo do slug."""
    name = (paths or FluxoPaths("events.jsonl", "live.html")).events_file
    return fluxo_dir_for_slug(projetos_root, slug) / name


def live_html_path(
    projetos_root: Path,
    slug: str,
    *,
    paths: FluxoPaths | None = None,
) -> Path:
    """Path de ``live.html`` sob a pasta fluxo do slug."""
    name = (paths or FluxoPaths("events.jsonl", "live.html")).live_html
    return fluxo_dir_for_slug(projetos_root, slug) / name


def resolve_projetos_root(
    explicit: Path | None,
    *,
    repo_root: Path,
    tree: str = "claude",
) -> Path:
    """Resolve raiz de projetos (``.claude/projetos`` ou ``.cursor/projetos``)."""
    if explicit is not None:
        return Path(explicit)
    if tree == "cursor":
        return repo_root / ".cursor" / "projetos"
    return repo_root / ".claude" / "projetos"


def load_contract_or_default(
    contract_path: Path | None,
    *,
    repo_root: Path,
) -> FluxoEventsContract:
    """Carrega contrato do path ou do default na raiz do repo."""
    path = contract_path or (repo_root / "fluxo-events.yaml")
    return FluxoEventsContract.load(path)
