"""
Configuração centralizada de pipeline. Troque de ambiente alterando PIPELINE_ENV.

Uso:
    config = PipelineConfig.from_env()
    df.write.saveAsTable(config.bronze_table("orders"))

Ambientes:
    PIPELINE_ENV=local  → config/environments/local.yaml
    PIPELINE_ENV=dev    → config/environments/dev.yaml
    PIPELINE_ENV=prd    → config/environments/prd.yaml
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path

# O canônico não distribui dependências de desenvolvimento; PyYAML não inclui stubs.
import yaml  # type: ignore[import-untyped]


@dataclass
class PipelineConfig:
    environment: str

    # Databricks / cloud
    workspace_url: str = ""
    cluster_id: str = ""
    catalog: str = ""

    # Schemas / paths
    schema_bronze: str = "bronze"
    schema_silver: str = "silver"
    schema_gold: str = "gold"
    schema_quarantine: str = "bronze"
    table_quarantine: str = "quarantine"

    # Local paths (modo local)
    data_root: str = "data"
    path_raw: str = "data/raw"
    path_bronze: str = "data/bronze"
    path_silver: str = "data/silver"
    path_gold: str = "data/gold"
    path_quarantine_local: str = "data/quarantine"

    # Unity Catalog volume (raw landing)
    volume_raw: str = ""

    # Spark
    spark_master: str = "local[*]"
    spark_app_name: str = "pipeline"

    # Schema evolution
    schema_evolution_strategy: str = "quarantine"  # quarantine | merge | fail

    # Notificações
    notifications_enabled: bool = False
    owner_email: str = ""
    slack_webhook_url: str = ""

    # Logging
    log_level: str = "INFO"
    log_format: str = "json"  # json | pretty

    # Qualidade
    quarantine_rate_threshold_pct: float = 1.0

    # Databricks Jobs
    job_name: str = ""

    # Airflow
    airflow_dag_id: str = ""

    # Metadados extras (carregados do YAML mas não mapeados acima)
    extra: dict = field(default_factory=dict)

    @classmethod
    def from_env(cls) -> "PipelineConfig":
        """Carrega config do ambiente definido em PIPELINE_ENV."""
        env = os.getenv("PIPELINE_ENV", "local")
        config_path = Path(__file__).parent / "environments" / f"{env}.yaml"

        if not config_path.exists():
            raise FileNotFoundError(
                f"Config não encontrada: {config_path}. "
                f"Crie config/environments/{env}.yaml ou ajuste PIPELINE_ENV."
            )

        with open(config_path) as f:
            data = yaml.safe_load(f)

        known_fields = {f.name for f in cls.__dataclass_fields__.values()}  # type: ignore[attr-defined]
        known = {k: v for k, v in data.items() if k in known_fields}
        extra = {k: v for k, v in data.items() if k not in known_fields}

        return cls(**known, extra=extra)

    def is_local(self) -> bool:
        return self.environment == "local"

    def is_cloud(self) -> bool:
        return self.environment in ("dev", "prd")

    # -------------------------------------------------------------------------
    # Helpers de tabela (Unity Catalog 3-level namespace)
    # -------------------------------------------------------------------------

    def bronze_table(self, name: str) -> str:
        if self.is_local():
            return name
        return f"{self.catalog}.{self.schema_bronze}.{name}"

    def silver_table(self, name: str) -> str:
        if self.is_local():
            return name
        return f"{self.catalog}.{self.schema_silver}.{name}"

    def gold_table(self, name: str) -> str:
        if self.is_local():
            return name
        return f"{self.catalog}.{self.schema_gold}.{name}"

    def quarantine_table(self) -> str:
        if self.is_local():
            return "quarantine"
        return f"{self.catalog}.{self.schema_quarantine}.{self.table_quarantine}"

    # -------------------------------------------------------------------------
    # Helpers de path (modo local)
    # -------------------------------------------------------------------------

    def raw_path(self, filename: str = "") -> str:
        base = self.volume_raw if self.is_cloud() else self.path_raw
        return f"{base}/{filename}" if filename else base

    def bronze_path(self, table: str = "") -> str:
        base = self.path_bronze
        return f"{base}/{table}" if table else base
