---
description: >-
  Cria branch de trabalho no padrão tipo/escopo: fetch, sync ff-only do tronco,
  valida nome via git-hygiene.yaml, exige acordo explícito, sugere título de PR.
  Use quando o usuário pedir "nova branch", "criar branch", "sair do master",
  ou `/nova-branch`.
---

# /nova-branch — branch isolada no padrão do contrato

Fonte de validação (obrigatória — **não** duplique regex):

- YAML: [`git-hygiene.yaml`](../../git-hygiene.yaml)
- Python: `config.git_hygiene.contract.GitHygieneContract` (`is_valid_branch`)
- Fixtures A3: `tests/git_hygiene/fixtures/branches_valid.txt` e
  `tests/git_hygiene/fixtures/branches_invalid.txt`

Cheatsheet: `/git-ajuda` · rule: `git-hygiene`.

## Pré-condições (soft-block)

Antes de qualquer `git switch -c`, verifique e **pare** com mensagem didática se:

| Condição | Ação |
|---|---|
| `git fetch` falhou (rede) | Soft-block — não finja sync; peça retry / VPN |
| Working tree suja | Soft-block — oferecer: (a) commit com acordo, (b) stash com acordo, (c) descartar com acordo explícito, (d) abortar. **Nunca** `reset --hard` / `clean` sem “de acordo” |
| Branch `tipo/escopo` já existe | Soft-block — oferecer: switch para ela, outro nome, ou abortar |
| Tronco local atrás do remote e `--ff-only` falharia | Soft-block — sync primeiro ou resolver divergência com humano |
| Tronco divergente (não-ff) | Soft-block humano — não force-push no tronco |

## Fluxo (nesta ordem)

1. **`git fetch`** (origin ou remote default).
2. **Checar working tree** (`git status --porcelain`) **antes** de trocar de branch.
   Suja → soft-block com opções (nunca destrutivo sem acordo).
3. **Detectar tronco:** `git symbolic-ref refs/remotes/origin/HEAD` → fallback `master`
   (ou `main` se for o default real do remote).
4. **Sync do tronco com `--ff-only`:**
   ```bash
   git switch <tronco>
   git pull --ff-only
   ```
   Se falhar → soft-block (tabela acima).
5. **Propor nome** `tipo/escopo`:
   - Inferir `tipo` (`feat|fix|chore`) e escopo kebab da intenção/contexto quando houver.
   - Validar com o contrato:
     ```bash
     PYTHONPATH=. python3 -c "
     from config.git_hygiene.contract import GitHygieneContract
     c = GitHygieneContract.load('git-hygiene.yaml')
     name = 'feat/exemplo'
     print('OK' if c.is_valid_branch(name) else 'INVALID')
     "
     ```
   - Rejeitar inválidos alinhados a `branches_invalid.txt` (`tmp`, acento, >40,
     `nova-branch`, tipo fora da lista, data solta).
   - Nome de pessoa: limite humano (ver `branch.limits.person_name` no YAML) —
     perguntar se parecer nome próprio.
6. **Acordo explícito:** mostre o nome proposto e só então peça “de acordo?”.
   Sem acordo → não cria.
7. **Criar:** `git switch -c <tipo/escopo>` (a partir do tronco syncado).
8. **Título de PR sugerido** (não abre PR — isso é adapter / harness-ship):
   Padrão: `tipo(escopo): resumo` (resumo ≤ 72 chars; ver `pr_title` em `git-hygiene.yaml`).
   Validar com `c.is_valid_pr_title(...)` quando possível. Exemplo:
   `feat(gate-branch-isolada): soft-block GIT_PREFLIGHT nos agents`

## Saída esperada

```
Branch: feat/meu-escopo
Base:   master @ <sha curto> (ff-only ok)
Título PR sugerido: feat(meu-escopo): <resumo>
Próximo: implementar → /validar → revisor → commit (com acordo) → abrir PR (adapter scm)
```

## Invariantes

- Commit / push / stash / descartar: **somente com acordo** (rule `git-hygiene`).
- Não abrir PR neste comando.
- Não inventar tipos além de `feat|fix|chore`.
- Sempre citar a fonte `git-hygiene.yaml` quando rejeitar um nome.
