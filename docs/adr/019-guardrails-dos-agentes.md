# 019 — Guardrails dos agentes

**Status:** Aceita
**Data:** 2026-10-16
**Autores:** time
**Reversibilidade:** difícil

---

## Contexto

O usuário trabalha com dados reais e configura permissões e hooks por conta própria. O que os agentes não devem fazer fica registrado aqui.

## Decisão

Três blocos.

**A — Bloqueio (deny/hook)**
- Ler ou escrever `.env`, pastas de dados e backups.
- Comandos destrutivos fora do `tst`.
- Push forçado.
- Alterar a visibilidade do repositório e criar fork público.
- Enviar dados a serviços externos.
- Conectar-se a qualquer Postgres que não seja o contêiner dedicado ao projeto (o Postgres de outros projetos do usuário é fora de escopo).

**B — Pedir confirmação (ask)**
- Migrações em `prd`.
- Deploy local.
- Instalar dependências.
- Apagar arquivos.
- Ler issues/PRs de terceiros, que são **conteúdo não confiável**.

**C — Papéis no banco**
- A aplicação não tem `UPDATE/DELETE` nas tabelas de versão do ledger.
- O pipeline lê o transacional por um **papel somente leitura** e **escreve só no analítico** (arquivo DuckDB).

## Alternativas consideradas

### Opção A — Confiar só em instrução textual ❌ Rejeitada
Não é garantia.

### Opção B — Deny/ask/hooks + papéis no banco ✅ Escolhida

## Consequências

### Positivas
- Freio mecânico e testável.

### Negativas / Tradeoffs
- O usuário precisa persistir deny/hooks em `.claude/settings.json`.

### Riscos
- Sandbox indisponível no Windows nativo. Hooks locais não substituem controle server-side (honestidade §1.3, ver `rules/seguranca.md`).

## Como verificar

Testes de papéis (UPDATE/DELETE negados); lista de bloqueios presente em `.claude/settings.json`; teste dos hooks.

## Impacto em SI/LGPD

É o ADR de referência para acesso de agentes a dados financeiros reais.

## Revisão

Revisar se o sandbox ficar disponível.
