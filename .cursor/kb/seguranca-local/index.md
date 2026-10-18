---
domain: seguranca-local
description: Segurança de um sistema financeiro pessoal local-first — localhost, segredos, backup, comandos destrutivos, skills de terceiros e pacote do revisor
mcp_validated: null
confidence: null
---

# KB: Segurança local

Resume os ADRs 014, 017, 018, 019 e 020 como modelo de ameaça local. Complementa `.claude/rules/seguranca.md` (que é o contrato transversal).

## Tópicos cobertos

- **Localhost apenas:** serviços escutam só em `127.0.0.1`; validação de Host.
- **Segredos:** `.env` fora do git, gitleaks no pre-commit, senha de admin do banco fora do `.env`.
- **Backup** criptografado com age, chave privada fora do PC, backup antes de sessões que alterem esquema/dados.
- **Comandos destrutivos:** confirmação obrigatória; só em `tst`.
- **Skills de terceiros:** revisar antes de instalar.
- **Pacote do revisor** sem dado real, `.env`, dumps ou backups.
- **Aplicação:** Argon2id, sessão no servidor, cookie HttpOnly + SameSite, CSRF, CORS restrito, rate limit de login.

## Tópicos detalhados

| Arquivo | Tópico |
|---|---|
| [backup-restore.md](backup-restore.md) | Backup e restauração do Postgres com age |
| [api-seguranca.md](api-seguranca.md) | Segurança da API FastAPI (ADR 020) |
| [segredos-gitleaks.md](segredos-gitleaks.md) | Segredos, .env e gitleaks (ADR 018) |

## Quick Reference

Ver [quick-reference.md](quick-reference.md).

## Nota de validação

Criado sem acesso à Context-7 MCP (`mcp_validated`/`confidence` ficam `null`).
