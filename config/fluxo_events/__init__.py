"""Kernel fluxo-events — telemetria live SDD (emit/render/truncate fail-soft)."""

from __future__ import annotations

from config.fluxo_events.contract import (
    FORBIDDEN_SLA_LATENCY_KEYS,
    REQUIRED_EVENT_TYPES,
    FluxoEventsContract,
    FluxoLimits,
    FluxoPaths,
    SddPhase,
)
from config.fluxo_events.slug import slug_from_prompt_path

__all__ = [
    "FORBIDDEN_SLA_LATENCY_KEYS",
    "REQUIRED_EVENT_TYPES",
    "FluxoEventsContract",
    "FluxoLimits",
    "FluxoPaths",
    "SddPhase",
    "slug_from_prompt_path",
]
