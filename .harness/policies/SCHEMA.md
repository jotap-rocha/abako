# Schema — `.harness/policies/` (seed install-harness)

## Layout

```
.harness/policies/
└── project_profile.yaml   # families[] extras opt-in; KEEP no re-install
```

## `project_profile.yaml`

```yaml
# vazio (sem extras):
families:

# com extras:
families:
  - cloud-cli-extra
```

**Não** use `families: []` — o loader YAML stdlib interpreta `[]` como string.

- `seed: true` no stack_map → 1º install COPY; re-install = KEEP
- Core (`shell`, `docker`, `git`, `sql-cli`, `databricks-cli`, `terraform`, `k8s`)
  é always-on via `agent-policies.yaml` — não precisa listar aqui
- Ortogonal a `.harness/data-check/` (kernel DE) e a `DE-A002`
