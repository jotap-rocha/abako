"""Collect — executa comando do critério e grava prova (LWW + cap fail)."""

from __future__ import annotations

import subprocess
from dataclasses import dataclass
from pathlib import Path

from config.evidence_gate.audit import (
    AuditEvent,
    append_audit_event,
    summarize_command,
    utc_now_iso,
)
from config.evidence_gate.contract import EvidenceGateContract
from config.evidence_gate.manifest import (
    CriterionEvidence,
    TaskManifest,
    load_task_manifest,
    relative_log_path,
    save_task_manifest,
)

DEFAULT_CONTRACT = Path(__file__).resolve().parents[2] / "evidence-gate.yaml"


@dataclass(frozen=True, slots=True)
class CollectOutcome:
    """Resultado de um collect."""

    task_id: str
    criterion_id: str
    exit_code: int
    log_path: Path
    collect_ok: bool
    invalid_cap: bool = False


def collect_criterion(
    *,
    root: Path,
    task_id: str,
    criterion_id: str,
    command: str | None = None,
    test_paths: tuple[str, ...] = (),
    contract_path: Path | None = None,
    cwd: Path | None = None,
) -> CollectOutcome:
    """Executa o comando e atualiza manifesto/log/audit (LWW)."""
    contract = EvidenceGateContract.load(contract_path or DEFAULT_CONTRACT)
    root = root.resolve()
    root.mkdir(parents=True, exist_ok=True)
    (root / contract.paths.tasks_dir).mkdir(parents=True, exist_ok=True)
    (root / contract.paths.logs_dir).mkdir(parents=True, exist_ok=True)

    existing_command = None
    existing_tests: tuple[str, ...] = ()
    manifest_file = root / contract.paths.tasks_dir / f"{task_id}.yaml"
    if manifest_file.is_file():
        try:
            current = load_task_manifest(root, task_id)
            try:
                prev = current.criterion(criterion_id)
                existing_command = prev.command
                existing_tests = prev.test_paths
            except KeyError:
                pass
        except (ValueError, FileNotFoundError):
            current = TaskManifest(task_id=task_id, criteria=())
    else:
        current = TaskManifest(task_id=task_id, criteria=())

    resolved_command = command or existing_command
    if not resolved_command or not resolved_command.strip():
        raise ValueError(
            f"collect exige --command ou comando prévio no manifesto "
            f"(task={task_id} criterion={criterion_id})"
        )
    resolved_tests = test_paths or existing_tests
    rel_log = relative_log_path(task_id, criterion_id)
    abs_log = root / rel_log
    abs_log.parent.mkdir(parents=True, exist_ok=True)

    max_bytes = contract.limits.max_log_bytes
    fail_on_exceed = contract.limits.fail_on_exceed
    exit_code, invalid_cap, bytes_written = _run_and_capture(
        command=resolved_command,
        log_path=abs_log,
        max_bytes=max_bytes,
        cwd=cwd,
    )

    collect_ok = exit_code == 0 and not invalid_cap
    if invalid_cap and fail_on_exceed:
        collect_ok = False
        # Remove log truncado — prova parcial inválida (G3)
        if abs_log.is_file():
            abs_log.unlink()
        # Marca critério inválido no manifesto sem exit 0
        criterion = CriterionEvidence(
            id=criterion_id,
            command=resolved_command.strip(),
            test_paths=resolved_tests,
            exit_code=exit_code if exit_code != 0 else 1,
            log_path=rel_log,
            invalid_cap=True,
        )
    else:
        criterion = CriterionEvidence(
            id=criterion_id,
            command=resolved_command.strip(),
            test_paths=resolved_tests,
            exit_code=exit_code,
            log_path=rel_log,
            invalid_cap=False,
        )

    updated = current.with_criterion(criterion)
    save_task_manifest(root, updated)

    append_audit_event(
        root,
        AuditEvent(
            timestamp=utc_now_iso(),
            task_id=task_id,
            criterion_id=criterion_id,
            exit_code=criterion.exit_code if criterion.exit_code is not None else 1,
            log_path=rel_log,
            command_summary=summarize_command(resolved_command),
            collect_ok=collect_ok,
            invalid_cap=invalid_cap,
        ),
        audit_file=contract.paths.audit_file,
    )

    return CollectOutcome(
        task_id=task_id,
        criterion_id=criterion_id,
        exit_code=criterion.exit_code if criterion.exit_code is not None else 1,
        log_path=abs_log if abs_log.is_file() else root / rel_log,
        collect_ok=collect_ok,
        invalid_cap=invalid_cap,
    )


def _run_and_capture(
    *,
    command: str,
    log_path: Path,
    max_bytes: int,
    cwd: Path | None,
) -> tuple[int, bool, int]:
    """Roda shell command; falha se stdout+stderr excederem cap."""
    proc = subprocess.Popen(
        command,
        shell=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        cwd=str(cwd) if cwd else None,
    )
    assert proc.stdout is not None
    written = 0
    invalid_cap = False
    with log_path.open("wb") as handle:
        while True:
            chunk = proc.stdout.read(65536)
            if not chunk:
                break
            if written + len(chunk) > max_bytes:
                # escreve só o que cabe para diagnóstico local, depois marca inválido
                remain = max_bytes - written
                if remain > 0:
                    handle.write(chunk[:remain])
                    written += remain
                invalid_cap = True
                proc.kill()
                break
            handle.write(chunk)
            written += len(chunk)
    exit_code = proc.wait()
    if invalid_cap:
        return exit_code if exit_code != 0 else 1, True, written
    return exit_code, False, written
