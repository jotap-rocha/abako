---
# Git Hygiene — carrega SEMPRE (sem paths: — regra global)
---

# Git Hygiene (controle de versão)

Regra **transversal** e **agnóstica de SCM** (Azure Repos, GitHub, etc.). A escolha de CLI
(`az` vs `gh`) é do adapter `scm` — esta rule não crava um provedor.

Fonte única de regex e tipos: `git-hygiene.yaml` na raiz do repositório.
Cheatsheet de uma página: `docs/cheatsheets/git-hygiene-cheatsheet.md` · atalho `/git-ajuda`.

## Invariantes

1. **Branch isolada** — não edite no tronco (`master`/`main`/default do remote) sem acordo
   explícito do usuário. Preferir `/nova-branch`.
2. **Nome de branch** — `tipo/escopo-kebab` com tipos `feat|fix|chore`; validar contra
   `git-hygiene.yaml` (não duplicar regex na prosa).
3. **Título de PR** — `tipo(escopo): resumo` (resumo ≤ 72). É o ponto de controle formal
   (commits locais podem ser livres com sugestão Conventional Commits).
4. **Sem segredo no diff** — nunca commit de PAT, chave, `.env` com secret real. Heurística
   local em `.githooks/pre-commit` (bloqueante); tokens só via env/secret manager.
5. **Acordo explícito** antes de:
   - `git commit`
   - `git push`
   - `git stash`
   - descartar working tree (`reset --hard`, `clean`, restore destrutivo)
6. **Soft-block `GIT_PREFLIGHT`** — antes de editar em fluxos harness/Dev Loop: fetch →
   tronco → sync `--ff-only` → working tree limpa → branch de trabalho. Falha → oferecer
   `/nova-branch`; não seguir como se estivesse sync.
7. **Limites reais (§1.3)** — sem Edit policies / branch protection, nenhum gate impede de
   fato; `--no-verify` e clone sem hooks contornam. Não prometa bloqueio server-side.

## O que esta rule NÃO faz

- Não escolhe Azure vs GitHub (use detecção de remote / pergunta se ambíguo).
- Não cria tag `prod-*` (fora da Fase 1).
- Não substitui `Edit policies` nem branch protection.
