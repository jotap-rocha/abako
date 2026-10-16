# Adapter SCM + abertura de PR híbrida

Fonte de detecção: `config.git_hygiene.scm.detect_scm` · rule: `git-hygiene` (agnóstica).

## Detecção

```bash
PYTHONPATH=. python3 -c "
from config.git_hygiene.scm import detect_scm
print(detect_scm('$(git remote get-url origin)'))
"
```

| Resultado | Significado |
|---|---|
| `azure` | remote contém `dev.azure.com` ou `visualstudio.com` |
| `github` | remote contém `github.com` |
| `ambiguous` | perguntar ao usuário (`scm: azure \| github`) |

## SI — tokens

- PAT / tokens: **somente** variável de ambiente ou secret manager.
- Nunca hardcoded, nunca em logs, nunca em URL query string.
- Exemplos de env (nomes ilustrativos — não versionar valores):
  - Azure: `AZURE_DEVOPS_EXT_PAT` / `AZURE_DEVOPS_PAT`
  - GitHub: `GH_TOKEN` / `GITHUB_TOKEN`

## Fluxo híbrido — Azure (`az`)

1. Verificar CLI: `az account show` (ou `az devops configure -l`).
2. Se autenticado, preferir create + squash quando a API permitir:
   ```bash
   az repos pr create \
     --title "tipo(escopo): resumo" \
     --description "$(cat .azuredevops/pull_request_template.md)" \
     --source-branch "$(git branch --show-current)" \
     --target-branch "$(git symbolic-ref --short refs/remotes/origin/HEAD | sed 's#^origin/##')" \
     --squash true
   ```
   (Flags exatas podem variar por versão da CLI — valide com `az repos pr create -h`.)
3. Se já existir PR da branch, **informe a URL** em vez de duplicar (`az repos pr list`).
4. Se CLI não autenticada: prepare payload para a UI (título + corpo do template + checklist).

## Fluxo híbrido — GitHub (`gh`)

1. Verificar: `gh auth status`.
2. Se autenticado:
   ```bash
   gh pr create --title "tipo(escopo): resumo" --body-file .azuredevops/pull_request_template.md
   ```
   Preferência de squash no merge (quando for mergear): `gh pr merge --squash`.
   (Em repos GitHub sem template Azure, use corpo equivalente do checklist do cheatsheet.)
3. Se já existir PR: `gh pr view --json url` e informe.
4. Sem auth: payload para a UI (compare URL + título/corpo).

## Wiring

- `/nova-branch` sugere o título; **não** abre PR.
- `harness-ship` (e agents de build) usam este fluxo após acordo de push.
- Prefixo `Merged PR NNN:` permanece aberto — não automatizar changelog aqui.
