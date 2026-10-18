# 024 — Implementação dos guardrails dos agentes

**Status:** Aceita
**Data:** 2026-10-17
**Autores:** time
**Reversibilidade:** difícil

---

## Contexto

O ADR 019 definiu o que os agentes não podem fazer. Faltava a implementação mecânica e ajustes: push forçado não precisa ser bloqueado, comandos destrutivos em `prd` passam pelo crivo do usuário e envio a serviços externos é proibido.

## Decisão

- Nova família `abako` em `agent-policies.yaml` (fonte única), com hook `PreToolUse` para **Bash e PowerShell**.
- **Deny:** ler/escrever `.env`, `data/`, `backups/`, `*.duckdb`, dumps, chaves age; remoção recursiva forçada (inclui PowerShell); `curl`/`wget`/`Invoke-WebRequest` etc. para fora de localhost; `gh repo edit --visibility`, `gh repo fork`, `gh repo delete`; Postgres na porta 5432 (outro projeto).
- **Ask:** `git commit`, `git push` (incluindo `--force`, que **não** é bloqueado), qualquer `psql`/`pg_*`, DML/DDL via psql, migração em `prd`, `deploy-local`, instalar dependências, apagar arquivos, ler issues/PRs de terceiros.
- Regras de arquivo (`Read/Edit/Write` de `.env*`, `data/`, `backups/`, `*.duckdb`, `*.dump`, `*.age`) e a lista `ask` ficam estáticas em `.claude/settings.json`; o gerador cobre só o `deny` de Bash.
- **Convenção:** o contêiner do projeto usa a porta **5433** (definida no `.env`); a 5432 é de outro projeto e fica bloqueada.
- Dados enviados a serviços externos, quando inevitável, devem ser **sintéticos**.

## Alternativas consideradas

### Opção A — Só instruções textuais ❌ Rejeitada
Não é garantia.

### Opção B — Bloquear push forçado ❌ Rejeitada pelo usuário
Fica como confirmação.

### Opção C — Família `abako` + permissões estáticas ✅ Escolhida

## Consequências

### Positivas
- Freio mecânico para dados reais, com fonte única do `deny` de Bash.

### Negativas / Tradeoffs
- Regex de shell é contornável (ex.: ler o arquivo por um script Python); proteção parcial. O mais seguro continua sendo o agente nunca receber credenciais de `prd`.
- Regex de shell gera falsos positivos: um comando que apenas *menciona* um padrão (por exemplo, texto de heredoc) pode ser bloqueado. Prefira criar arquivos pelas ferramentas de escrita.
- O hook trata `ask` com exit 0; a confirmação efetiva depende também de `permissions.ask`.
- `curl` para localhost é permitido pelo hook; `Bash(curl https:*)` está no `deny`.

## Impacto em SI/LGPD

Referência para acesso de agentes a dados financeiros reais.

## Revisão

Revisar se surgir sandbox no Windows ou controle server-side. Ver `rules/seguranca.md` §1.3.
