# Agent-policies — cheatsheet (1 página)

Fonte: [`agent-policies.yaml`](../../agent-policies.yaml) · CLI: `python -m config.agent_policies check|generate`

## O que é

Freio **local** dual-runtime (Claude + Cursor) contra ops destrutivas de shell/CLI.
Soft policy `seguranca` permanece; githooks continuam secrets-only.

## Declaração §1.3 — limites reais

Deny/hooks **não** são Edit policies / branch protection. Contornos reais: bypass env,
clone sem hooks, desligar hooks no IDE. Objetivo: caminho seguro default + auditabilidade —
sem falsa sensação de bloqueio server-side.

## Severidade

| Classe | Exemplos | Comportamento |
|---|---|---|
| deny-hard | `rm -rf`, `docker compose down -v`, `dropdb`, `terraform destroy`, `kubectl delete --all` | Bloqueia; engine down → **fail closed** |
| ask | `git push --force`, `git reset --hard`, `databricks … delete` | Confirmação humana; engine down → **fail open** |

## Bypass

```bash
HARNESS_ALLOW_DESTRUCTIVE=1
```

Short-circuit consciente de deny-hard + log de audit (family/pattern; sem secret/PII).
DDL/prod continua exigindo ADR + confirmação humana (`seguranca`).

## Core vs extras

- **Core always-on:** `shell`, `docker`, `git`, `sql-cli`, `databricks-cli`, `terraform`, `k8s`
- **Extras opt-in:** `.harness/policies/project_profile.yaml` → `families: [cloud-cli-extra, …]`
- Seed `seed: true` KEEP no re-install

## Dual runtime

| Runtime | Artefato |
|---|---|
| Claude | `permissions.deny` + PreToolUse (`.claude/hooks/agent_policies_pretooluse.sh`) |
| Cursor | `.cursor/hooks.json` → `beforeShellExecution` |

Mesmo catálogo/severity; adapters finos; generate único.

**Nota (UI):** Cursor honra `permission: ask`. No Claude, ask retorna exit 0 + JSON
`permission=ask` — o runtime pode não pausar como o Cursor; deny-hard continua exit 2.

## Ortogonal a DE-A002

| Camada | Escopo |
|---|---|
| agent-policies | Bash/CLI de **sessão** (IDE hooks) |
| `DE-A002` | Código **versionado** DE (canonical_data_check) |

Não unificar kernels — só cross-link.

## Comandos

```bash
python -m config.agent_policies check
python -m config.agent_policies generate --dry-run
python -m config.agent_policies generate --out-dir /tmp/policies-out
```
