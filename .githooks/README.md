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

## Caminho para gitleaks

Esta heurística é MVP. Para plugar [gitleaks](https://github.com/gitleaks/gitleaks)
depois:

1. Adicione `gitleaks` como dep opcional / CI.
2. Troque o corpo de `pre-commit` por `gitleaks protect --staged` (ou equivalente).
3. Mantenha mensagens didáticas (o que fazer + por quê).

Não implementado neste MVP de propósito (custo de adoção / binário).
