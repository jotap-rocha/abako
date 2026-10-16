"""Registry dos pacotes de check."""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path

from config.canonical_data_check.checks.package_a import check_package_a
from config.canonical_data_check.checks.package_b import check_package_b
from config.canonical_data_check.checks.package_c import check_package_c, detect_airflow
from config.canonical_data_check.checks.package_d import check_package_d
from config.canonical_data_check.checks.package_e import check_package_e
from config.canonical_data_check.findings import Finding
from config.canonical_data_check.scanner import TextFile

PackageCheck = Callable[[Path, tuple[TextFile, ...]], tuple[Finding, ...]]

PACKAGE_CHECK_REGISTRY: dict[str, PackageCheck] = {
    "A": check_package_a,
    "B": check_package_b,
    "C": check_package_c,
    "D": check_package_d,
    "E": check_package_e,
}

__all__ = [
    "PACKAGE_CHECK_REGISTRY",
    "PackageCheck",
    "check_package_a",
    "check_package_b",
    "check_package_c",
    "check_package_d",
    "check_package_e",
    "detect_airflow",
]
