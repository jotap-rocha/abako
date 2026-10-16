---
domain: fastapi
description: Padrões FastAPI — routers finos, service layer, dependency injection, error contracts, async
mcp_validated: "2026-06-27"
confidence: 0.93
---

# KB: FastAPI

Base de conhecimento de padrões FastAPI para APIs assíncronas, modulares e seguras.
Princípio central: **rota fina + service layer** — routers não contêm lógica de negócio.

## Conceitos

| Arquivo | Tópico |
|---|---|
| [router-vs-service.md](concepts/router-vs-service.md) | Separação de responsabilidades: rota declara, service executa |
| [dependency-injection.md](concepts/dependency-injection.md) | `Depends()` para DB, auth, config — sem global state |
| [async-patterns.md](concepts/async-patterns.md) | async/await, connection pools, background tasks |
| [error-contracts.md](concepts/error-contracts.md) | HTTPException padronizada, handlers globais, schema de erro |

## Padrões

| Arquivo | Tópico |
|---|---|
| [thin-router.md](patterns/thin-router.md) | Router com validação + 1 chamada de service — nada mais |
| [service-layer.md](patterns/service-layer.md) | Service com lógica de negócio, testável sem HTTP |
| [health-check.md](patterns/health-check.md) | /health com verificação de dependências (DB, cache, LLM) |
| [openapi-contract.md](patterns/openapi-contract.md) | Schemas Pydantic, tags, summary, responses declarados |

## Quick Reference

Ver [quick-reference.md](quick-reference.md) — layout canônico, invariantes (FA-01…FA-06),
decision tree async vs sync. Ler só se a tarefa exigir esse nível de detalhe operacional.
