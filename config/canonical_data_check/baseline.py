"""Baseline ratchet, compare e waivers em ``.harness/data-check/``."""

from __future__ import annotations

import json
import os
from dataclasses import dataclass
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any

from config.canonical_data_check.constants import (
    DATA_CHECK_DIRNAME,
    DEFAULT_PROFILE,
    EXIT_BLOCKERS,
    EXIT_OK,
    EXIT_USAGE,
)
from config.canonical_data_check.de_marker import (
    DATABRICKS_DLT_PROFILE,
    DATABRICKS_MULTI_PROFILE,
    DATABRICKS_SDP_PROFILE,
)
from config.canonical_data_check.engine import validate_project
from config.canonical_data_check.findings import Finding, ValidationResult, sort_findings
from config.canonical_data_check.waivers_yaml import (
    WaiversYamlError,
    parse_waivers_document,
)


BASELINE_FILENAME = "baseline.json"
PROFILE_FILENAME = "project_profile.yaml"
WAIVERS_FILENAME = "waivers.yaml"
BASELINE_VERSION = 1


@dataclass(frozen=True, slots=True)
class BaselineEntry:
    """Entrada sanitizada persistida no baseline (sem message/secrets)."""

    rule_id: str
    path: str
    severity: str
    fingerprint: str

    def to_dict(self) -> dict[str, str]:
        return {
            "rule_id": self.rule_id,
            "path": self.path,
            "severity": self.severity,
            "fingerprint": self.fingerprint,
        }


@dataclass(frozen=True, slots=True)
class Waiver:
    """Waiver pontual — só é ativo com owner + expiry futura (ou hoje)."""

    rule_id: str
    owner: str
    expiry: date
    reason: str = ""

    @property
    def is_active(self) -> bool:
        today_utc = datetime.now(timezone.utc).date()
        return bool(self.owner.strip()) and self.expiry >= today_utc


def fingerprint_of(rule_id: str, path: str) -> str:
    """Chave estável de ratchet: rule_id + path sem sufixo ``:linha``.

    Paths como ``pipelines/x.sql:3`` e ``pipelines/x.sql:4`` colapsam na
    mesma dívida (evita falso "novo" por shift de linha).
    """
    return f"{rule_id}|{_path_without_lineno(path)}"


def _path_without_lineno(path: str) -> str:
    if ":" not in path:
        return path
    head, _, tail = path.rpartition(":")
    if tail.isdigit() and head:
        return head
    return path


def data_check_dir(project_root: Path) -> Path:
    return project_root / DATA_CHECK_DIRNAME


class BaselineStoreError(ValueError):
    """baseline.json existe mas está ilegível/corrompido."""


def write_baseline(
    project_path: Path | str,
    *,
    contract_path: Path | str | None = None,
    profile: str = DEFAULT_PROFILE,
) -> ValidationResult:
    """Grava snapshot dos blockers atuais em ``.harness/data-check/``.

    Idempotente e atômico. Exit 0 se a escrita suceder (dívida registrada,
    não enforce). Nunca persiste ``message`` (evita secrets raw).
    """
    root = Path(project_path)
    validation = validate_project(
        root, contract_path=contract_path, profile=profile
    )
    if validation.exit_code == EXIT_USAGE:
        return validation

    entries = _entries_from_findings(validation.findings)
    effective_profile = validation.profile
    payload: dict[str, object] = {
        "version": BASELINE_VERSION,
        "profile": effective_profile,
        "generated_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "findings": [entry.to_dict() for entry in entries],
    }
    effective_profiles = _profiles_for_baseline(effective_profile)
    if effective_profiles:
        payload["profiles"] = effective_profiles

    target = data_check_dir(root)
    target.mkdir(parents=True, exist_ok=True)
    _atomic_write_text(
        target / BASELINE_FILENAME,
        json.dumps(payload, ensure_ascii=True, indent=2, sort_keys=False) + "\n",
    )
    _ensure_project_profile(target / PROFILE_FILENAME, effective_profile)
    _ensure_waivers_seed(target / WAIVERS_FILENAME)

    return ValidationResult(
        exit_code=EXIT_OK,
        findings=validation.findings,
        profile=effective_profile,
    )


def compare_project(
    project_path: Path | str,
    *,
    contract_path: Path | str | None = None,
    profile: str = DEFAULT_PROFILE,
) -> ValidationResult:
    """Compara findings atuais vs baseline + waivers (ratchet).

    - finding novo (não baselineado e sem waiver válido) → fail
    - finding no baseline → status ``baseline`` (não quebra)
    - waiver ativo (owner + expiry >= hoje) → status ``waived``
    - waiver incompleto/expirado → não silencia
    """
    root = Path(project_path)
    validation = validate_project(
        root, contract_path=contract_path, profile=profile
    )
    if validation.exit_code == EXIT_USAGE:
        return validation

    try:
        known = _load_baseline_fingerprints(data_check_dir(root) / BASELINE_FILENAME)
    except BaselineStoreError as exc:
        return ValidationResult(
            exit_code=EXIT_USAGE,
            findings=(
                Finding(
                    rule_id="DE-USAGE",
                    severity="blocker",
                    status="fail",
                    path=str(data_check_dir(root) / BASELINE_FILENAME),
                    message=str(exc),
                ),
            ),
            profile=profile,
        )
    active_waivers = _load_active_waiver_rule_ids(
        data_check_dir(root) / WAIVERS_FILENAME
    )

    remapped: list[Finding] = []
    for finding in validation.findings:
        if finding.status != "fail":
            remapped.append(finding)
            continue
        if finding.rule_id in active_waivers:
            remapped.append(_with_status(finding, "waived"))
            continue
        fp = fingerprint_of(finding.rule_id, finding.path)
        if fp in known:
            remapped.append(_with_status(finding, "baseline"))
            continue
        remapped.append(finding)

    ordered = sort_findings(remapped)
    has_blocker = any(
        item.status == "fail" and item.severity == "blocker" for item in ordered
    )
    return ValidationResult(
        exit_code=EXIT_BLOCKERS if has_blocker else EXIT_OK,
        findings=ordered,
        profile=validation.profile,
    )


def _profiles_for_baseline(effective_profile: str) -> list[str]:
    """Expande perfis cloud/multi em IDs canônicos com ordem determinística."""
    if effective_profile == DATABRICKS_MULTI_PROFILE:
        return sorted([DATABRICKS_DLT_PROFILE, DATABRICKS_SDP_PROFILE])
    if effective_profile in {DATABRICKS_DLT_PROFILE, DATABRICKS_SDP_PROFILE}:
        return [effective_profile]
    return []


def _entries_from_findings(findings: tuple[Finding, ...]) -> list[BaselineEntry]:
    entries: list[BaselineEntry] = []
    for finding in findings:
        if finding.status != "fail" or finding.severity != "blocker":
            continue
        entries.append(
            BaselineEntry(
                rule_id=finding.rule_id,
                path=finding.path,
                severity=finding.severity,
                fingerprint=fingerprint_of(finding.rule_id, finding.path),
            )
        )
    return sorted(entries, key=lambda item: (item.rule_id, item.path))


def _with_status(finding: Finding, status: str) -> Finding:
    return Finding(
        rule_id=finding.rule_id,
        severity=finding.severity,
        status=status,
        path=finding.path,
        message=finding.message,
    )


def _load_baseline_fingerprints(path: Path) -> frozenset[str]:
    if not path.is_file():
        return frozenset()
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except OSError as exc:
        raise BaselineStoreError(f"falha ao ler baseline: {exc}") from exc
    except json.JSONDecodeError as exc:
        raise BaselineStoreError(
            f"baseline.json corrompido ou inválido: {exc.msg}"
        ) from exc
    findings = payload.get("findings", [])
    if not isinstance(findings, list):
        raise BaselineStoreError("baseline.json: campo 'findings' deve ser lista")
    fps: set[str] = set()
    for item in findings:
        if not isinstance(item, dict):
            continue
        fp = item.get("fingerprint")
        if isinstance(fp, str) and fp:
            # Normaliza fingerprints legados que incluíam :linha
            if "|" in fp:
                fp_rule, _, fp_path = fp.partition("|")
                fps.add(fingerprint_of(fp_rule, fp_path))
            else:
                fps.add(fp)
            continue
        entry_rule = item.get("rule_id")
        entry_path = item.get("path")
        if isinstance(entry_rule, str) and isinstance(entry_path, str):
            fps.add(fingerprint_of(entry_rule, entry_path))
    return frozenset(fps)


def _load_active_waiver_rule_ids(path: Path) -> frozenset[str]:
    waivers = load_waivers(path)
    return frozenset(w.rule_id for w in waivers if w.is_active)


def load_waivers(path: Path) -> tuple[Waiver, ...]:
    """Carrega waivers; entradas inválidas são ignoradas (não silenciam)."""
    if not path.is_file():
        return ()
    try:
        text = path.read_text(encoding="utf-8")
        items = parse_waivers_document(text)
    except (OSError, WaiversYamlError):
        return ()

    parsed: list[Waiver] = []
    for item in items:
        waiver = _parse_waiver(item)
        if waiver is not None:
            parsed.append(waiver)
    return tuple(parsed)


def _parse_waiver(item: Any) -> Waiver | None:
    """Só aceita waiver com rule_id, owner não-vazio e expiry parseável.

    Waivers incompletos retornam None — caller não os trata como ativos.
    """
    if not isinstance(item, dict):
        return None
    rule_id = item.get("rule_id")
    owner = item.get("owner")
    expiry_raw = item.get("expiry")
    if not isinstance(rule_id, str) or not rule_id.strip():
        return None
    if not isinstance(owner, str) or not owner.strip():
        return None
    if expiry_raw is None:
        return None
    expiry = _parse_expiry(expiry_raw)
    if expiry is None:
        return None
    reason = item.get("reason", "")
    reason_str = reason if isinstance(reason, str) else ""
    return Waiver(
        rule_id=rule_id.strip(),
        owner=owner.strip(),
        expiry=expiry,
        reason=reason_str,
    )


def _parse_expiry(value: Any) -> date | None:
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    if isinstance(value, str):
        try:
            return date.fromisoformat(value.strip()[:10])
        except ValueError:
            return None
    return None


def _ensure_project_profile(path: Path, profile: str) -> None:
    if path.is_file():
        return
    content = (
        "# Perfil normativo do projeto-filho (seed/runtime)\n"
        f"profile: {profile}\n"
    )
    _atomic_write_text(path, content)


def _ensure_waivers_seed(path: Path) -> None:
    if path.is_file():
        return
    content = (
        "# Waivers pontuais: exigem owner + expiry (YYYY-MM-DD).\n"
        "# Sem owner/expiry (ou expiry passado) o waiver NÃO silencia blocker.\n"
        "waivers: []\n"
    )
    _atomic_write_text(path, content)


def _atomic_write_text(path: Path, content: str) -> None:
    """Escrita atômica via arquivo temporário + replace (POSIX)."""
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(f".{path.name}.{os.getpid()}.tmp")
    try:
        tmp.write_text(content, encoding="utf-8")
        os.replace(tmp, path)
    finally:
        if tmp.exists():
            tmp.unlink(missing_ok=True)
