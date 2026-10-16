"""Manifesto por task sob ``evidencias/tasks/<id>.yaml``."""

from __future__ import annotations

from dataclasses import dataclass, field, replace
from pathlib import Path
from typing import Mapping

from config.evidence_gate.yaml_loader import load_mapping


@dataclass(frozen=True, slots=True)
class CriterionEvidence:
    """Prova atual de um critério (LWW)."""

    id: str
    command: str
    test_paths: tuple[str, ...]
    exit_code: int | None
    log_path: str
    waiver_human: bool = False
    waiver_reason: str | None = None
    invalid_cap: bool = False


@dataclass(frozen=True, slots=True)
class TaskManifest:
    """Manifesto atual de uma task."""

    task_id: str
    criteria: tuple[CriterionEvidence, ...] = field(default_factory=tuple)

    def criterion(self, criterion_id: str) -> CriterionEvidence:
        for item in self.criteria:
            if item.id == criterion_id:
                return item
        raise KeyError(f"critério ausente: {criterion_id}")

    def with_criterion(self, criterion: CriterionEvidence) -> TaskManifest:
        """LWW: substitui critério de mesmo id ou acrescenta."""
        others = [c for c in self.criteria if c.id != criterion.id]
        others.append(criterion)
        return replace(self, criteria=tuple(others))


def manifest_path(root: Path, task_id: str) -> Path:
    return root / "tasks" / f"{task_id}.yaml"


def relative_log_path(task_id: str, criterion_id: str) -> str:
    return f"logs/{task_id}/{criterion_id}.log"


def load_task_manifest(root: Path, task_id: str) -> TaskManifest:
    path = manifest_path(root, task_id)
    if not path.is_file():
        raise FileNotFoundError(f"manifesto ausente: {path}")
    return task_manifest_from_mapping(load_mapping(path))


def task_manifest_from_mapping(data: Mapping[str, object]) -> TaskManifest:
    raw_id = data.get("task_id")
    if isinstance(raw_id, int) and not isinstance(raw_id, bool):
        task_id = str(raw_id)
    elif isinstance(raw_id, str) and raw_id.strip():
        task_id = raw_id.strip()
    else:
        raise ValueError("task_id deve ser string não vazia")
    criteria_raw = data.get("criteria")
    if not isinstance(criteria_raw, dict):
        raise ValueError("criteria deve ser mapping")
    criteria: list[CriterionEvidence] = []
    for cid, raw in criteria_raw.items():
        if not isinstance(cid, str):
            raise ValueError("criteria keys devem ser string")
        criteria.append(_build_criterion(cid, raw))
    return TaskManifest(task_id=task_id, criteria=tuple(criteria))


def save_task_manifest(root: Path, manifest: TaskManifest) -> Path:
    path = manifest_path(root, manifest.task_id)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(_dump_manifest(manifest), encoding="utf-8")
    return path


def _build_criterion(cid: str, raw: object) -> CriterionEvidence:
    path = f"criteria.{cid}"
    if not isinstance(raw, dict):
        raise ValueError(f"{path} deve ser mapping")
    mapping: Mapping[str, object] = raw
    crit_id = str(mapping.get("id") or cid).strip()
    command = _require_string(mapping, "command", f"{path}.command")
    test_paths = _optional_string_list(mapping.get("test_paths"))
    exit_raw = mapping.get("exit_code")
    exit_code: int | None
    if exit_raw is None:
        exit_code = None
    elif isinstance(exit_raw, int) and not isinstance(exit_raw, bool):
        exit_code = exit_raw
    else:
        raise ValueError(f"{path}.exit_code deve ser int ou ausente")
    log = mapping.get("log_path")
    if not isinstance(log, str) or not log.strip():
        log = relative_log_path("unknown", crit_id)
    waiver = mapping.get("waiver")
    waiver_human = False
    waiver_reason: str | None = None
    if waiver is not None:
        if not isinstance(waiver, dict):
            raise ValueError(f"{path}.waiver deve ser mapping")
        human = waiver.get("human")
        if human is not True:
            raise ValueError(f"{path}.waiver.human deve ser true")
        reason = waiver.get("reason")
        if not isinstance(reason, str) or not reason.strip():
            raise ValueError(f"{path}.waiver.reason obrigatório")
        waiver_human = True
        waiver_reason = reason.strip()
    invalid_cap = mapping.get("invalid_cap") is True
    return CriterionEvidence(
        id=crit_id,
        command=command,
        test_paths=test_paths,
        exit_code=exit_code,
        log_path=log.strip(),
        waiver_human=waiver_human,
        waiver_reason=waiver_reason,
        invalid_cap=invalid_cap,
    )


def _dump_manifest(manifest: TaskManifest) -> str:
    lines = [f"task_id: {_quote(manifest.task_id)}", "criteria:"]
    if not manifest.criteria:
        lines.append("  {}")
        return "\n".join(lines) + "\n"
    for crit in sorted(manifest.criteria, key=lambda c: c.id):
        lines.append(f"  {crit.id}:")
        lines.append(f"    id: {crit.id}")
        lines.append(f"    command: {_quote(crit.command)}")
        lines.append("    test_paths:")
        if crit.test_paths:
            for tp in crit.test_paths:
                lines.append(f"      - {_quote(tp)}")
        # vazio: chave sem filhos (loader → {}); ver _optional_string_list
        if crit.exit_code is not None:
            lines.append(f"    exit_code: {crit.exit_code}")
        lines.append(f"    log_path: {_quote(crit.log_path)}")
        if crit.invalid_cap:
            lines.append("    invalid_cap: true")
        if crit.waiver_human:
            lines.append("    waiver:")
            lines.append("      human: true")
            lines.append(f"      reason: {_quote(crit.waiver_reason or '')}")
    return "\n".join(lines) + "\n"


def _quote(value: str) -> str:
    escaped = value.replace("\\", "\\\\").replace('"', '\\"')
    return f'"{escaped}"'


def _require_string(data: Mapping[str, object], key: str, path: str) -> str:
    value = data.get(key)
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{path} deve ser string não vazia")
    return value.strip()


def _optional_string_list(value: object) -> tuple[str, ...]:
    if value is None:
        return ()
    if value == [] or value == "[]":
        return ()
    if isinstance(value, dict) and not value:
        # YAML `test_paths:` sem filhos → mapping vazio no loader stdlib
        return ()
    if not isinstance(value, list):
        raise ValueError("test_paths deve ser lista")
    if not all(isinstance(item, str) and item.strip() for item in value):
        raise ValueError("test_paths deve conter strings")
    return tuple(item.strip() for item in value)
