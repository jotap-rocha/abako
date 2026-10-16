"""Constantes públicas da CLI canonical-data-check."""

from __future__ import annotations

EXIT_OK = 0
EXIT_BLOCKERS = 1
EXIT_USAGE = 2

DEFAULT_PROFILE = "spark-yarn-airflow"

# Runtime no projeto-alvo (filho); templates seed ficam no canônico.
DATA_CHECK_DIRNAME = ".harness/data-check"
