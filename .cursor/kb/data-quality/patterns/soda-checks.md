---
topic: soda-checks
confidence: null
mcp_validated: null
---

# Checks Declarativos com Soda (Soda Core / Soda Checks Language - SodaCL)

## Quando usar

Soda quando o time quer checks **legíveis por não-engenheiros** (YAML declarativo, sem Python),
com foco forte em freshness/volume/schema (os 3 pilares de
`concepts/pipeline-observability.md`) além das dimensões clássicas de qualidade.

## Instalação

```bash
uv add soda-core-spark   # ou soda-core-postgres, soda-core-snowflake, etc.
```

## Configuração da conexão

```yaml
# configuration.yml
data_source orders_ds:
  type: spark
  method: session
```

## Checks declarativos (SodaCL)

```yaml
# checks/orders_silver.yml
checks for orders_silver:
  # Completude
  - missing_count(order_id) = 0
  - missing_count(customer_id) = 0

  # Unicidade
  - duplicate_count(order_id) = 0

  # Validade
  - invalid_percent(amount) < 1%:
      valid min: 0.01
      valid max: 1000000
  - invalid_count(status) = 0:
      valid values: [pending, confirmed, shipped, delivered, cancelled]

  # Volume (anomaly detection automática sobre histórico)
  - row_count > 0
  - anomaly score for row_count < default

  # Freshness
  - freshness(_ingested_at) < 24h

  # Schema
  - schema:
      warn:
        when schema changes: [column add]
      fail:
        when schema changes: [column delete, column type change]
```

## Rodando um scan

```bash
soda scan -d orders_ds -c configuration.yml checks/orders_silver.yml
```

Saída inclui pass/fail por check + exit code não-zero se algum check `fail` — plugável
diretamente em CI/orquestrador sem parsing extra.

## Integração em pipeline Python

```python
from soda.scan import Scan

def run_soda_scan(config_path: str, checks_path: str, data_source: str) -> bool:
    scan = Scan()
    scan.set_data_source_name(data_source)
    scan.add_configuration_yaml_file(config_path)
    scan.add_sodacl_yaml_file(checks_path)

    exit_code = scan.execute()
    scan_results = scan.get_scan_results()

    for check in scan_results["checks"]:
        if check["outcome"] == "fail":
            log.warning("soda_check_failed", check=check["name"], outcome=check["outcome"])

    return exit_code == 0
```

## Checks com severidade (warn vs fail)

```yaml
checks for orders_silver:
  - missing_count(order_id) = 0:
      name: "order_id nunca nulo"
      # sem qualificador = fail por padrão

  - duplicate_percent(customer_id) < 5%:
      warn: when > 2%
      fail: when > 5%
```

`warn` mapeia para severidade `log`/`quarantine` do pipeline; `fail` mapeia para severidade
`fail` bloqueante (ver tabela de severidade em `pipeline/patterns/data-quality.md`).

## Checks orientados a dataset inteiro (dataset-level)

```yaml
checks for orders_silver:
  - row_count same as yesterday for orders_silver_yesterday:
      threshold: 20%   # tolera variação de até 20% dia-a-dia
```

## Gotchas

- **`anomaly score` precisa de histórico** — os primeiros scans não têm baseline suficiente;
  não confie no anomaly detection nos primeiros ~14 dias de execução.
- **`freshness()` usa o relógio da máquina que roda o scan**, não o timezone da fonte — alinhe
  timezone explicitamente se pipeline e fonte estão em regiões diferentes.
- **Schema check com `column type change` como `fail` quebra pipeline em mudanças cosméticas**
  (ex.: `int` → `bigint` sem perda de dado) — avalie se isso deveria ser `warn` no seu contexto.
- **Soda Core é open-source; Soda Cloud (dashboards/alertas centralizados) é produto pago** — não
  assuma que features de UI do Soda Cloud existem no Soda Core standalone.
