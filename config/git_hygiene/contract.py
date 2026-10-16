"""Validador do contrato Git Hygiene — regex só via git-hygiene.yaml."""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Pattern

from config.git_hygiene.yaml_loader import load_mapping


@dataclass(frozen=True)
class GitHygieneContract:
    """Contrato imutável carregado da fonte única YAML."""

    version: int
    branch_pattern: Pattern[str]
    branch_types: tuple[str, ...]
    scope_pattern: Pattern[str]
    scope_max_length: int
    forbidden_scopes: frozenset[str]
    forbidden_scope_patterns: tuple[Pattern[str], ...]
    person_name_limit_note: str
    pr_title_pattern: Pattern[str]
    summary_max_length: int

    @classmethod
    def load(cls, path: Path | str) -> GitHygieneContract:
        data = load_mapping(Path(path))
        return cls.from_mapping(data)

    @classmethod
    def from_mapping(cls, data: dict[str, Any]) -> GitHygieneContract:
        branch = _require_mapping(data, "branch")
        scope = _require_mapping(branch, "scope")
        limits = _require_mapping(branch, "limits")
        pr_title = _require_mapping(data, "pr_title")

        types_raw = branch.get("types")
        if not isinstance(types_raw, list) or not types_raw:
            raise ValueError("branch.types deve ser lista não vazia")

        forbidden_raw = scope.get("forbidden") or []
        if not isinstance(forbidden_raw, list):
            raise ValueError("branch.scope.forbidden deve ser lista")

        forbidden_patterns_raw = scope.get("forbidden_patterns") or []
        if not isinstance(forbidden_patterns_raw, list):
            raise ValueError("branch.scope.forbidden_patterns deve ser lista")

        person_note = limits.get("person_name")
        if not isinstance(person_note, str) or not person_note.strip():
            raise ValueError("branch.limits.person_name deve ser string não vazia")

        return cls(
            version=int(data.get("version", 1)),
            branch_pattern=_compile(branch, "pattern", "branch.pattern"),
            branch_types=tuple(str(t) for t in types_raw),
            scope_pattern=_compile(scope, "pattern", "branch.scope.pattern"),
            scope_max_length=int(scope["max_length"]),
            forbidden_scopes=frozenset(str(item) for item in forbidden_raw),
            forbidden_scope_patterns=tuple(
                re.compile(str(pat)) for pat in forbidden_patterns_raw
            ),
            person_name_limit_note=person_note.strip(),
            pr_title_pattern=_compile(pr_title, "pattern", "pr_title.pattern"),
            summary_max_length=int(pr_title["summary_max_length"]),
        )

    def is_valid_branch(self, name: str) -> bool:
        match = self.branch_pattern.fullmatch(name)
        if match is None:
            return False
        branch_type = match.group(1)
        if branch_type not in self.branch_types:
            return False
        scope = match.group(2)
        return self._is_valid_scope(scope)

    def is_valid_pr_title(self, title: str) -> bool:
        match = self.pr_title_pattern.fullmatch(title)
        if match is None:
            return False
        branch_type = match.group(1)
        if branch_type not in self.branch_types:
            return False
        scope = match.group(2)
        summary = match.group(3)
        if not self._is_valid_scope(scope):
            return False
        if len(summary) > self.summary_max_length:
            return False
        if not summary.strip():
            return False
        return True

    def _is_valid_scope(self, scope: str) -> bool:
        if len(scope) > self.scope_max_length:
            return False
        if self.scope_pattern.fullmatch(scope) is None:
            return False
        if scope in self.forbidden_scopes:
            return False
        for pattern in self.forbidden_scope_patterns:
            if pattern.fullmatch(scope):
                return False
        return True


def _require_mapping(data: dict[str, Any], key: str) -> dict[str, Any]:
    value = data.get(key)
    if not isinstance(value, dict):
        raise ValueError(f"{key} deve ser mapping")
    return value


def _compile(section: dict[str, Any], key: str, label: str) -> Pattern[str]:
    raw = section.get(key)
    if not isinstance(raw, str) or not raw:
        raise ValueError(f"{label} deve ser string não vazia")
    return re.compile(raw)
