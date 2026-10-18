---
domain: react-pwa
description: Frontend React + TypeScript como PWA instalável — manifest, service worker, formulários com validação, testes e tratamento de decimal em JavaScript
mcp_validated: null
confidence: null
---

# KB: React PWA

Base de conhecimento do `fin-frontend` (`.claude/agents/fin/fin-frontend.md`). Escopo definido nos ADRs 011, 015 e 023.

## Tópicos cobertos

- **Estrutura** de app Vite + React + TypeScript estrito; cliente TS gerado do OpenAPI do FastAPI.
- **PWA:** manifest, service worker, instalação no Chrome Android e limites do iOS. **Sem escrita offline no MVP.**
- **Formulários:** padrões de formulário com validação (formulário dinâmico por tipo de transação).
- **Testes:** de componente (Vitest + React Testing Library) e de ponta a ponta (Playwright, poucas jornadas).
- **Decimal no JavaScript:** valor monetário como texto ou biblioteca decimal, **nunca `number`**.

## Fronteiras

- Regra financeira → backend/SQL (`.claude/kb/postgres-financeiro/`), nunca aqui.
- Segurança de sessão, CORS e CSRF → `.claude/kb/seguranca-local/` e ADR 020.

## Tópicos detalhados

| Arquivo | Tópico |
|---|---|
| [openapi-cliente.md](openapi-cliente.md) | Cliente TS gerado do OpenAPI |
| [pwa.md](pwa.md) | PWA: manifest, service worker, sem escrita offline |
| [formularios.md](formularios.md) | Formulário dinâmico por tipo, RHF + Zod, dinheiro como texto |

## Quick Reference

Ver [quick-reference.md](quick-reference.md).

## Nota de validação

Criado sem acesso à Context-7 MCP (`mcp_validated`/`confidence` ficam `null`). Os conteúdos específicos (versões, comandos) serão preenchidos na SPEC-001 e na SPEC do frontend; não foram inventados aqui.
