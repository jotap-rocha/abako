"""Detecção do adapter SCM pelo URL do remote (agnóstico da rule git-hygiene)."""

from __future__ import annotations

from enum import Enum


class ScmKind(str, Enum):
    """Provedor SCM detectado a partir do remote URL."""

    AZURE = "azure"
    GITHUB = "github"
    AMBIGUOUS = "ambiguous"


def detect_scm(remote_url: str) -> ScmKind:
    """Classifica o remote como azure, github ou ambiguous.

    Azure: ``dev.azure.com`` ou ``visualstudio.com`` (inclui SSH ``ssh.dev.azure.com``).
    GitHub: ``github.com``.
    Qualquer outro (ou URL vazia) → ``ambiguous`` (perguntar ao usuário).
    """
    url = (remote_url or "").strip().lower()
    if not url:
        return ScmKind.AMBIGUOUS

    is_azure = (
        "dev.azure.com" in url
        or "visualstudio.com" in url
        or "vs-ssh.visualstudio.com" in url
    )
    is_github = "github.com" in url

    if is_azure and not is_github:
        return ScmKind.AZURE
    if is_github and not is_azure:
        return ScmKind.GITHUB
    return ScmKind.AMBIGUOUS
