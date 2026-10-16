"""Contrato tipado e imutável de fluxo-events (telemetria live SDD)."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Mapping

from config.fluxo_events.yaml_loader import load_mapping

REQUIRED_EVENT_TYPES: tuple[str, ...] = (
    "phase_enter",
    "phase_exit",
    "agent_enter",
    "agent_exit",
    "task_enter",
    "task_exit",
    "ship_truncate",
)

FORBIDDEN_SLA_LATENCY_KEYS: frozenset[str] = frozenset(
    {
        "sla",
        "sla_ms",
        "sla_seconds",
        "latency",
        "latency_ms",
        "max_latency",
        "target_latency",
        "latency_target",
        "p99_latency",
        "max_latency_ms",
    }
)


@dataclass(frozen=True, slots=True)
class FluxoLimits:
    """Caps e default de truncate no ship (G3-a / G4-b)."""

    max_events_bytes: int
    truncate_keep_default: int


@dataclass(frozen=True, slots=True)
class SddPhase:
    """Uma fase do mapa estrutural SDD 0–4."""

    phase: int
    slug: str
    agents: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class FluxoPaths:
    """Nomes relativos sob a pasta ``fluxo/`` do projeto."""

    events_file: str
    live_html: str


@dataclass(frozen=True, slots=True)
class FluxoEventsContract:
    """Fonte normativa carregada de ``fluxo-events.yaml``."""

    version: int
    limits: FluxoLimits
    sdd_map: tuple[SddPhase, ...]
    dev_loop_map: tuple[SddPhase, ...]
    event_types: tuple[str, ...]
    paths: FluxoPaths

    @classmethod
    def load(cls, path: Path | str) -> FluxoEventsContract:
        """Carrega e valida o contrato a partir de um path YAML."""
        return cls.from_mapping(load_mapping(Path(path)))

    @classmethod
    def from_mapping(cls, data: Mapping[str, object]) -> FluxoEventsContract:
        """Valida um mapping no boundary e cria o contrato imutável."""
        _reject_sla_latency_keys(data, "root")
        version = _require_positive_int(data, "version", "version")
        limits = _build_limits(_require_non_empty_mapping(data, "limits", "limits"))
        sdd_map = _build_phase_map(
            data.get("sdd_map"),
            "sdd_map",
            expected_phases=frozenset({0, 1, 2, 3, 4}),
            max_phase_key=4,
        )
        dev_loop_map = _build_phase_map(
            data.get("dev_loop_map"),
            "dev_loop_map",
            expected_phases=frozenset({0, 1, 2, 3, 4, 5, 6}),
            max_phase_key=6,
        )
        event_types = _build_event_types(data)
        paths_raw = data.get("paths")
        if paths_raw is None:
            paths = FluxoPaths(events_file="events.jsonl", live_html="live.html")
        else:
            paths = _build_paths(_as_mapping(paths_raw, "paths"))
        return cls(
            version=version,
            limits=limits,
            sdd_map=sdd_map,
            dev_loop_map=dev_loop_map,
            event_types=event_types,
            paths=paths,
        )


def _build_limits(data: Mapping[str, object]) -> FluxoLimits:
    _reject_sla_latency_keys(data, "limits")
    return FluxoLimits(
        max_events_bytes=_require_positive_int(
            data, "max_events_bytes", "limits.max_events_bytes"
        ),
        truncate_keep_default=_require_positive_int(
            data, "truncate_keep_default", "limits.truncate_keep_default"
        ),
    )


def _build_phase_map(
    value: object,
    path: str,
    *,
    expected_phases: frozenset[int],
    max_phase_key: int,
) -> tuple[SddPhase, ...]:
    """Aceita mapping ``{fase: {slug, agents}}`` (compatível com o loader mínimo)."""
    if isinstance(value, list):
        raise ValueError(
            f"{path} deve ser mapping por fase (não lista) — "
            "loader mínimo não parseia list-of-maps"
        )
    lo, hi = min(expected_phases), max(expected_phases)
    if not isinstance(value, dict) or not value:
        raise ValueError(f"{path} deve ser mapping não vazio (fases {lo}–{hi})")
    if not all(isinstance(key, str) for key in value):
        raise ValueError(f"{path} deve ter somente chaves string")
    phases: list[SddPhase] = []
    seen: set[int] = set()
    for key, item in value.items():
        item_path = f"{path}.{key}"
        phase_num = _phase_key_to_int(key, item_path, max_phase_key=max_phase_key)
        if phase_num in seen:
            raise ValueError(f"{path}: fase {phase_num} duplicada")
        seen.add(phase_num)
        mapping = _as_mapping(item, item_path)
        slug = _require_string(mapping, "slug", f"{item_path}.slug")
        agents = _require_string_list(mapping, "agents", f"{item_path}.agents")
        phases.append(SddPhase(phase=phase_num, slug=slug, agents=agents))
    if seen != set(expected_phases):
        raise ValueError(
            f"{path} deve cobrir fases {lo}–{hi} exatamente (got {sorted(seen)})"
        )
    return tuple(sorted(phases, key=lambda p: p.phase))


def _build_sdd_map(value: object, path: str) -> tuple[SddPhase, ...]:
    """Compat: mapa SDD 0–4."""
    return _build_phase_map(
        value,
        path,
        expected_phases=frozenset({0, 1, 2, 3, 4}),
        max_phase_key=4,
    )


def _phase_key_to_int(key: str, path: str, *, max_phase_key: int = 4) -> int:
    allowed = {str(i) for i in range(max_phase_key + 1)}
    if key not in allowed:
        raise ValueError(
            f"{path}: chave de fase deve ser exatamente '0'..'{max_phase_key}'"
        )
    return int(key)


def _build_event_types(data: Mapping[str, object]) -> tuple[str, ...]:
    types = _require_string_list(data, "event_types", "event_types")
    missing = [name for name in REQUIRED_EVENT_TYPES if name not in types]
    if missing:
        raise ValueError(
            "event_types deve incluir: " + ", ".join(REQUIRED_EVENT_TYPES)
            + f" (faltando: {', '.join(missing)})"
        )
    return types


def _build_paths(data: Mapping[str, object]) -> FluxoPaths:
    return FluxoPaths(
        events_file=_require_string(data, "events_file", "paths.events_file"),
        live_html=_require_string(data, "live_html", "paths.live_html"),
    )


def _reject_sla_latency_keys(data: Mapping[str, object], where: str) -> None:
    for key in data:
        lowered = key.lower()
        if (
            key in FORBIDDEN_SLA_LATENCY_KEYS
            or "latency" in lowered
            or lowered.startswith("sla")
            or lowered.endswith("_sla")
        ):
            raise ValueError(
                f"{where}: campo '{key}' proibido (G1-c / AC15 — "
                "sem alvo numérico de SLA/latência no contrato)"
            )


def _as_mapping(value: object, path: str) -> Mapping[str, object]:
    if not isinstance(value, dict):
        raise ValueError(f"{path} deve ser mapping")
    if not all(isinstance(key, str) for key in value):
        raise ValueError(f"{path} deve ter somente chaves string")
    return value


def _require_non_empty_mapping(
    data: Mapping[str, object],
    key: str,
    path: str,
) -> Mapping[str, object]:
    mapping = _as_mapping(data.get(key), path)
    if not mapping:
        raise ValueError(f"{path} deve ser mapping não vazio")
    return mapping


def _require_string(data: Mapping[str, object], key: str, path: str) -> str:
    value = data.get(key)
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{path} deve ser string não vazia")
    return value.strip()


def _require_string_list(
    data: Mapping[str, object],
    key: str,
    path: str,
) -> tuple[str, ...]:
    value = data.get(key)
    if not isinstance(value, list) or not value:
        raise ValueError(f"{path} deve ser lista não vazia")
    if not all(isinstance(item, str) and item.strip() for item in value):
        raise ValueError(f"{path} deve conter somente strings não vazias")
    return tuple(item.strip() for item in value)


def _require_positive_int(data: Mapping[str, object], key: str, path: str) -> int:
    value = data.get(key)
    if not isinstance(value, int) or isinstance(value, bool) or value < 1:
        raise ValueError(f"{path} deve ser inteiro positivo")
    return value

