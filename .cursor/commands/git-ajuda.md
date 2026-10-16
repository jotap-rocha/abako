---
description: >-
  Mostra o contrato Git Hygiene de uma página (branch, título de PR, hooks, acordo
  explícito, §1.3). Use quando o usuário pedir "git ajuda", "como nomeia branch",
  "padrão de PR", "cheatsheet git", ou `/git-ajuda`.
---

# /git-ajuda — contrato Git Hygiene

Leia e **exiba** (ou resuma fielmente) o cheatsheet canônico:

[`docs/cheatsheets/git-hygiene-cheatsheet.md`](../../docs/cheatsheets/git-hygiene-cheatsheet.md)

Fonte de regex / tipos: [`git-hygiene.yaml`](../../git-hygiene.yaml) — **não** invente padrões
diferentes dos do YAML.

## O que sempre incluir na resposta

1. **Declaração §1.3** — nenhum gate impede de fato sem Edit policies / branch protection;
   gates locais são contornáveis; objetivo = caminho certo fácil + errado visível.
2. Formato de branch: `feat|fix|chore` / escopo kebab ≤ 40.
3. Título de PR: `tipo(escopo): resumo` (resumo ≤ 72).
4. Acordo explícito para commit, push, stash e descartar.
5. Apontar `/nova-branch` para criar branch e o adapter SCM (`azure` \| `github`) para abrir PR.

Não crave Azure DevOps na prosa da rule — o cheatsheet é agnóstico; o adapter escolhe a CLI.
