# config/

Engines Python do canônico. Cada contrato YAML da raiz tem um pacote aqui que o carrega e
aplica. Os pacotes são importados como `config.<pacote>` (não mover sem migrar imports,
testes e o manifest do `install-harness`).

| Pacote / pasta | Contrato (raiz) | CLI |
|---|---|---|
| `agent_policies/` | `agent-policies.yaml` | `python -m config.agent_policies check\|generate` |
| `evidence_gate/` | `evidence-gate.yaml` | `python -m config.evidence_gate collect\|check` |
| `fluxo_events/` | `fluxo-events.yaml` | `python -m config.fluxo_events emit\|render\|truncate` |
| `git_hygiene/` | `git-hygiene.yaml` | (usado por `/nova-branch`, hooks e adapter SCM) |
| `data_engineering/` | `data-engineering.yaml` | loader tipado do contrato DE |
| `canonical_data_check/` | `data-engineering.yaml` | `python -m config.canonical_data_check validate\|baseline\|compare\|report\|explain` |

Outros:

- `environments/` — `dev.yaml`, `local.yaml`, `prd.yaml` (config por ambiente).
- `pipeline_config.py` — leitura da config de pipeline.
- `templates/` — scaffolds copiados para projetos filhos (ex.: `cloud-secrets/`).
- Seeds de cada kernel ficam em `<pacote>/templates/` e vão para `.harness/` no filho.

Cheatsheets dos kernels: [`docs/cheatsheets/`](../docs/cheatsheets/).
