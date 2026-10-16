# 022 — Repositório público, CI/CD e escopo da documentação

**Status:** Aceita
**Data:** 2026-10-16
**Autores:** time
**Reversibilidade:** difícil

---

## Contexto

O usuário quer repositório GitHub público e CI/CD. Hoje o repositório é privado; a mudança de visibilidade é decisão do usuário (ADR 019).

## Decisão

- Repositório **público**.
- **GitHub-hosted runners**, **sem segredos no CI**, Postgres efêmero no job.
- Ações fixadas por SHA, permissões mínimas, Dependabot, actionlint + zizmor, aprovação de PR de fork.
- **Sem `pull_request_target`**, `main` protegida, **sem self-hosted runner**.
- CD = releases com tag + `scripts/deploy-local` manual, que **recusa sem backup recente**.
- **`.claude/`, `CLAUDE.md`, `docs/adr/`, `tests/contracts/` e `fixtures/` são públicos**, técnicos e anônimos. Uma varredura de termos pessoais cobre todos eles.
- Rascunhos de brainstorm **não são persistidos**: foram consolidados nestes ADRs, no PRD e nos contratos. Isso substitui a ideia original de manter `docs/` no `.gitignore`.

## Alternativas consideradas

### Opção A — Docs públicas descaracterizadas à parte ❌ Rejeitada
Mais trabalho, sem ganho.

### Opção B — Runner self-hosted ❌ Rejeitada
Risco com repositório público.

### Opção C — Tudo público e anônimo, CI sem segredos ✅ Escolhida

## Consequências

### Positivas
- Nada pessoal no público; a varredura é automatizável.

### Riscos
- Qualquer termo pessoal que escape à varredura fica público.

## Premissas

Runners gratuitos para repositório público (anúncio do GitHub em dez/2025; reconfirmar se mudar).

## Fora de escopo

CD automático; ambientes remotos.

## Como verificar

Varredura de termos pessoais em `fixtures/`, `tests/contracts/`, `.claude/`, `CLAUDE.md` e `docs/adr/`; revisão dos workflows por actionlint/zizmor.

## Impacto em SI/LGPD

Antes de tornar o repositório público, auditar o histórico do git.

## Revisão

Revisar se o GitHub mudar o modelo de runners gratuitos.
