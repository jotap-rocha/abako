---
domain: seguranca-local
topic: api-seguranca
confidence: null
mcp_validated: null
---

# abako — segurança da API (ADR 020)

Checklist (rubrica C1–C6):
1. **user_id só da sessão.** Dependência `usuario_atual` injeta; nenhuma rota lê `user_id` do corpo, query ou path. Toda consulta filtra por ele (INV-13). Teste: usuário A nunca vê dado de B.
2. **Senha:** Argon2id via pwdlib (mínimo OWASP: 19 MiB, t=2, p=1). Nunca em log, nunca em resposta.
3. **Sessão no servidor** (tabela no Postgres): id aleatório longo no cookie `HttpOnly; SameSite=Lax|Strict; Secure` quando houver HTTPS; expiração e revogação.
4. **CSRF:** SameSite + checagem de `Origin` + token anti-CSRF nas rotas que mudam estado.
5. **CORS** restrito à origem do front; **Host** validado (TrustedHostMiddleware).
6. **Rate limit** no login (por IP e por usuário) com atraso crescente.
7. Escuta só em `127.0.0.1`. Sem cadastro público nem e-mail; usuários/senha por comando local.
8. Erros sem stack trace nem SQL; logs sem senha, dado pessoal ou valores.
9. Validação de entrada com Pydantic; valores monetários como `Decimal` vindos de string.

Testes obrigatórios: isolamento entre usuários, rate limit, CSRF sem token rejeitado, senha ausente de logs.

> Texto escrito a partir dos ADRs do projeto. Versões e flags de ferramentas externas devem ser conferidas na documentação atual (context7) ao implementar; não foram validadas aqui.
