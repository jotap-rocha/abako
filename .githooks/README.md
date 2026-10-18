# `.githooks/` — hooks locais do Git Hygiene (Fase 1 · Convenção)

| Hook | Comportamento MVP |
|---|---|
| `pre-commit` | Heurística leve de segredos — **bloqueante** (exit ≠ 0) |
| `commit-msg` | Aviso Conventional Commits — **não bloqueia** |
| `pre-push` | Aviso se push no tronco (`master`/`main`) — **não bloqueia** |

## Bootstrap (idempotente)

```bash
# Via helper do canônico:
./scripts/bootstrap-githooks.sh

# Ou manualmente:
git config core.hooksPath .githooks
```

No `/install-harness`, o Install Plan **pede confirmação** antes de configurar
`core.hooksPath` no projeto alvo.

## Limites (§1.3)

Hooks são locais e contornáveis (`--no-verify`, clone sem bootstrap). Não substituem
`Edit policies` / branch protection.

## Segredos detectados

O `pre-commit` **não imprime** o valor do segredo — só arquivo + tipo + o que fazer.
Se vazou no histórico: **rotacione** a credencial.

## gitleaks (ADR 018)

O `pre-commit` usa o [gitleaks](https://github.com/gitleaks/gitleaks) quando ele está
instalado (`winget install Gitleaks.Gitleaks`): roda `gitleaks git --pre-commit --staged`
com `.gitleaks.toml` (regras padrão + exceções estreitas). Se não achar o binário, avisa e
cai na heurística leve abaixo. Em Windows o hook também procura o binário na pasta do
winget, pois shells já abertos não enxergam o PATH novo.

Varredura completa (histórico e árvore), antes de mudar visibilidade ou publicar:

```bash
gitleaks git --redact --config .gitleaks.toml
gitleaks dir . --redact --config .gitleaks.toml
```

Exceções vão em `.gitleaks.toml` e só via PR, sempre estreitas (caminho ou valor exato).

Não implementado neste MVP de propósito (custo de adoção / binário).
