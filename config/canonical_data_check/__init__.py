"""CLI canonical-data-check — validate/baseline/compare/report/explain."""

from __future__ import annotations

from config.canonical_data_check.baseline import compare_project, write_baseline
from config.canonical_data_check.constants import (
    DATA_CHECK_DIRNAME,
    DEFAULT_PROFILE,
    EXIT_BLOCKERS,
    EXIT_OK,
    EXIT_USAGE,
)
from config.canonical_data_check.engine import validate_project
from config.canonical_data_check.findings import Finding, ValidationResult

__all__ = [
    "DATA_CHECK_DIRNAME",
    "DEFAULT_PROFILE",
    "EXIT_BLOCKERS",
    "EXIT_OK",
    "EXIT_USAGE",
    "Finding",
    "ValidationResult",
    "compare_project",
    "validate_project",
    "write_baseline",
]
