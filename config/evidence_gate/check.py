"""Check — valida manifesto + logs + evidencias_ref."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

from config.evidence_gate.contract import EvidenceGateContract
from config.evidence_gate.manifest import load_task_manifest

DEFAULT_CONTRACT = Path(__file__).resolve().parents[2] / "evidence-gate.yaml"


@dataclass(frozen=True, slots=True)
class CheckResult:
    """Resultado de um check de task."""

    ok: bool
    errors: tuple[str, ...]
    criteria_checked: int


def check_task(
    *,
    root: Path,
    task_id: str,
    contract_path: Path | None = None,
    entregas_path: Path | None = None,
    issue: int | None = None,
    ref_base: Path | None = None,
) -> CheckResult:
    """Valida manifesto da task sob ``root``."""
    contract = EvidenceGateContract.load(contract_path or DEFAULT_CONTRACT)
    errors: list[str] = []
    root = root.resolve()

    try:
        manifest = load_task_manifest(root, task_id)
    except FileNotFoundError as exc:
        return CheckResult(ok=False, errors=(str(exc),), criteria_checked=0)
    except ValueError as exc:
        return CheckResult(ok=False, errors=(str(exc),), criteria_checked=0)

    if manifest.task_id != str(task_id):
        errors.append(
            f"task_id do manifesto ({manifest.task_id}) != pedido ({task_id})"
        )

    if not manifest.criteria:
        errors.append(f"task {task_id}: manifesto sem criteria")

    checked = 0
    for crit in manifest.criteria:
        checked += 1
        prefix = f"criterion={crit.id}"

        if contract.check.require_test_path_or_waiver:
            if not crit.test_paths and not crit.waiver_human:
                errors.append(
                    f"{prefix}: sem path de teste e sem waiver humano"
                )
            if crit.waiver_human and not (crit.waiver_reason or "").strip():
                errors.append(f"{prefix}: waiver.reason obrigatório")

        if crit.invalid_cap:
            errors.append(f"{prefix}: prova inválida (log excedeu cap 2 MiB)")

        if contract.check.require_exit_zero:
            if crit.exit_code is None:
                errors.append(f"{prefix}: exit_code ausente (rode collect)")
            elif crit.exit_code != 0:
                errors.append(
                    f"{prefix}: exit_code={crit.exit_code} (exige 0)"
                )

        if contract.check.require_log_exists:
            log_abs = (root / crit.log_path).resolve()
            if not log_abs.is_file():
                errors.append(f"{prefix}: log ausente: {crit.log_path}")
            else:
                size = log_abs.stat().st_size
                if size > contract.limits.max_log_bytes:
                    errors.append(
                        f"{prefix}: log {crit.log_path} "
                        f"excede cap ({size} > {contract.limits.max_log_bytes})"
                    )

    if contract.check.require_evidencias_ref and entregas_path is not None:
        errors.extend(
            _check_evidencias_ref(
                entregas_path=entregas_path,
                issue=issue if issue is not None else _coerce_issue(task_id),
                expected_manifest=root / "tasks" / f"{task_id}.yaml",
                ref_base=ref_base or entregas_path.parent,
            )
        )

    return CheckResult(
        ok=not errors,
        errors=tuple(errors),
        criteria_checked=checked,
    )


def _coerce_issue(task_id: str) -> int:
    digits = "".join(ch for ch in task_id if ch.isdigit())
    if not digits:
        raise ValueError(
            "issue/task numérico obrigatório para validar evidencias_ref"
        )
    return int(digits)


def _check_evidencias_ref(
    *,
    entregas_path: Path,
    issue: int,
    expected_manifest: Path,
    ref_base: Path,
) -> list[str]:
    if not entregas_path.is_file():
        return [f"entregas ausente: {entregas_path}"]
    matched: dict[str, object] | None = None
    for line in entregas_path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        row = json.loads(line)
        if int(row.get("issue", -1)) == issue:
            matched = row
    if matched is None:
        return [f"evidencias_ref: linha issue={issue} ausente em entregas"]

    ref = matched.get("evidencias_ref")
    if not isinstance(ref, str) or not ref.strip():
        return [f"evidencias_ref ausente ou vazio na linha issue={issue}"]

    ref_path = Path(ref.strip())
    if not ref_path.is_absolute():
        ref_path = (ref_base / ref_path).resolve()
    else:
        ref_path = ref_path.resolve()

    if not ref_path.is_file():
        return [f"evidencias_ref quebrado (arquivo inexistente): {ref}"]

    expected = expected_manifest.resolve()
    if ref_path != expected:
        # aceita se for o mesmo arquivo via path relativo equivalente
        try:
            if ref_path.samefile(expected):
                return []
        except OSError:
            pass
        return [
            f"evidencias_ref aponta para {ref_path}, "
            f"esperado manifesto {expected}"
        ]
    return []
