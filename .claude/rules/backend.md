---
# Convenções do backend FastAPI e do SQL do abako
paths:
  - "backend/**"
  - "db/**"
---

# Backend

A camada web é fina: **roteia, valida, delega.** A regra financeira vive no SQL (views/funções em `db/`) e em `services/` apenas orquestra a chamada. Nunca no router.

- **Routers finos:** extraem/validam a entrada (Pydantic), chamam um service e formatam a saída. Zero regra de negócio ou SQL no router.
- **Contrato OpenAPI:** é a fonte do cliente TS do front. Mudou a API, regenere o cliente e versione o OpenAPI (ADR 015).
- **Dinheiro:** `Decimal` no Python, `NUMERIC` no banco, **texto** no JSON. Nunca `float` (INV-14).
- **Isolamento:** o `user_id` vem **sempre da sessão** (dependência do FastAPI), nunca do corpo ou da query da requisição. Toda consulta filtra por ele (INV-13).
- **Papel `app`:** sem `UPDATE/DELETE` nas tabelas de versão do ledger. Edição cria nova versão; exclusão é lógica (ADR 006, 019).
- **Config só via settings** (pydantic-settings). Nunca `os.environ` solto nem segredo hardcoded; tudo no `.env` (ADR 018).
- **Async de ponta a ponta:** handlers `async def`, sem chamada bloqueante no event loop.
- **Erros:** traduza falha de domínio em status HTTP correto; não vaze stack trace nem SQL cru.
- **Rede:** a API escuta só em `127.0.0.1`; CORS restrito, validação de Host, CSRF e rate limit de login (ADR 020).
- **Logs:** sem senha, sem dado pessoal e sem valores financeiros.
- **Migrações** em `db/`, versionadas e reversíveis; em `prd` pedem confirmação (ADR 019).
