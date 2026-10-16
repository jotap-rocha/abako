# 020 — Autenticação

**Status:** Aceita
**Data:** 2026-10-16
**Autores:** time
**Reversibilidade:** difícil

---

## Contexto

Login já na v1; não há cadastro público.

## Decisão

- **Argon2id** (pwdlib; mínimo OWASP: 19 MiB, t=2, p=1).
- **Sessão no servidor (Postgres)**; cookie HttpOnly + SameSite.
- **CSRF:** SameSite + checagem de Origin + token anti-CSRF.
- CORS restrito; validação de Host; rate limit de login.
- Autorização **sempre** pelo `user_id` da sessão.
- **Sem auto-cadastro nem e-mail:** usuários e recuperação de senha por **comando local**.

## Alternativas consideradas

### Opção A — JWT stateless ❌ Rejeitada
Difícil de revogar.

### Opção B — OAuth externo ❌ Rejeitada
Depende de serviço externo.

### Opção C — Sessão no servidor + Argon2id ✅ Escolhida

## Consequências

### Positivas
- Simples e seguro para uso local; escala para multiusuário depois.

## Premissas

Acesso só local.

## Fora de escopo

2FA; SSO; recuperação por e-mail.

## Como verificar

Teste de isolamento entre usuários (INV-13); senha nunca em log; testes de rate limit e CSRF.

## Impacto em SI/LGPD

Senha nunca em log; `user_id` nunca vindo do corpo da requisição.

## Revisão

Revisar se o acesso deixar de ser só local.
