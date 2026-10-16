"""Helpers de fechamento de task/ship para agents (collect→check + ref)."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from config.evidence_gate.check import CheckResult, check_task
from config.evidence_gate.collect import CollectOutcome, collect_criterion
from config.evidence_gate.contract import EvidenceGateContract
from config.evidence_gate.manifest import manifest_path

DEFAULT_CONTRACT = Path(__file__).resolve().parents[2] / "evidence-gate.yaml"


@dataclass(frozen=True, slots=True)
class CloseGateResult:
    """Resultado do gate de evidência antes de marcar task done."""

    ok: bool
    evidencias_ref: str | None
    check: CheckResult | None
    errors: tuple[str, ...]


def evidencias_ref_for(root: Path, task_id: str, *, relative_to: Path | None = None) -> str:
    """Path do manifesto para gravar em ``evidencias_ref``."""
    path = manifest_path(root, task_id).resolve()
    if relative_to is not None:
        try:
            return str(path.relative_to(relative_to.resolve()))
        except ValueError:
            return str(path)
    return str(path)


def require_evidencias_ref_field(record: dict[str, Any]) -> None:
    """Valida que a linha de entregas tem ``evidencias_ref`` não vazio."""
    ref = record.get("evidencias_ref")
    if not isinstance(ref, str) or not ref.strip():
        raise ValueError("entregas exige campo evidencias_ref (path do manifesto)")


def close_task_evidence_gate(
    *,
    root: Path,
    task_id: str,
    entregas_path: Path | None = None,
    issue: int | None = None,
    contract_path: Path | None = None,
    ref_base: Path | None = None,
    require_entregas: bool = True,
) -> CloseGateResult:
    """Roda ``check`` (e opcionalmente valida entregas) antes de fechar a task.

    Bloqueia se check ≠ 0. ``evidencias_ref`` deve apontar o manifesto.
    """
    contract = EvidenceGateContract.load(contract_path or DEFAULT_CONTRACT)
    errors: list[str] = []

    entregas = entregas_path
    if require_entregas and contract.check.require_evidencias_ref and entregas is None:
        errors.append(
            "fechamento exige --entregas (evidencias_ref obrigatório no contrato)"
        )
        return CloseGateResult(
            ok=False,
            evidencias_ref=None,
            check=None,
            errors=tuple(errors),
        )

    check = check_task(
        root=root,
        task_id=task_id,
        contract_path=contract_path or DEFAULT_CONTRACT,
        entregas_path=entregas,
        issue=issue,
        ref_base=ref_base or (entregas.parent if entregas else None),
    )
    if not check.ok:
        return CloseGateResult(
            ok=False,
            evidencias_ref=evidencias_ref_for(root, task_id, relative_to=ref_base),
            check=check,
            errors=check.errors,
        )

    ref = evidencias_ref_for(root, task_id, relative_to=ref_base)
    return CloseGateResult(
        ok=True,
        evidencias_ref=ref,
        check=check,
        errors=(),
    )


def revalidate_tasks_for_ship(
    *,
    root: Path,
    task_ids: list[str],
    contract_path: Path | None = None,
) -> CloseGateResult:
    """Revalida ``check`` de todas as tasks do fluxo (harness-ship)."""
    all_errors: list[str] = []
    last: CheckResult | None = None
    for tid in task_ids:
        result = check_task(
            root=root,
            task_id=tid,
            contract_path=contract_path or DEFAULT_CONTRACT,
            entregas_path=None,
            issue=None,
        )
        last = result
        if not result.ok:
            all_errors.extend(f"task={tid}: {e}" for e in result.errors)
    return CloseGateResult(
        ok=not all_errors,
        evidencias_ref=None,
        check=last,
        errors=tuple(all_errors),
    )


def append_entrega_with_ref(
    entregas_path: Path,
    record: dict[str, Any],
) -> None:
    """Append JSONL após validar ``evidencias_ref``."""
    require_evidencias_ref_field(record)
    entregas_path.parent.mkdir(parents=True, exist_ok=True)
    with entregas_path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(record, ensure_ascii=False) + "\n")


def collect_then_check(
    *,
    root: Path,
    task_id: str,
    criterion_id: str,
    command: str,
    test_paths: tuple[str, ...] = (),
    contract_path: Path | None = None,
    cwd: Path | None = None,
) -> tuple[CollectOutcome, CheckResult]:
    """Smoke de integração: collect → check (sem entregas)."""
    outcome = collect_criterion(
        root=root,
        task_id=task_id,
        criterion_id=criterion_id,
        command=command,
        test_paths=test_paths,
        contract_path=contract_path or DEFAULT_CONTRACT,
        cwd=cwd,
    )
    check = check_task(
        root=root,
        task_id=task_id,
        contract_path=contract_path or DEFAULT_CONTRACT,
    )
    return outcome, check
