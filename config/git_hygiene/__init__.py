"""Contrato Git Hygiene — carrega e aplica git-hygiene.yaml (fonte única)."""

from config.git_hygiene.contract import GitHygieneContract
from config.git_hygiene.scm import ScmKind, detect_scm

__all__ = ["GitHygieneContract", "ScmKind", "detect_scm"]
