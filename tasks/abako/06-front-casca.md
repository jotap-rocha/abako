# SPEC-012 (1/5): casca do frontend e login

**Status:** not started  
**Blocked by:** tasks/abako/05-login.md

## What to build

Frontend fino: projeto React + TypeScript, cliente TS gerado do OpenAPI, casca da PWA, tela de login/logout e base visual. O usuário dita e exemplifica os designs de tela nesta etapa.

## Acceptance criteria

- [ ] SPEC-012-AC-1: o cliente TS é gerado do OpenAPI e uma checagem falha se estiver defasado — tested by: tests/contracts/test_cliente_openapi.py::test_cliente_atualizado
- [ ] SPEC-012-AC-2: login e logout funcionam pela tela; logout limpa o cache da PWA — tested by: frontend/src/login/Login.test.tsx::logout_limpa_cache
- [ ] SPEC-012-AC-3: o front não contém regra de cálculo financeiro e trata dinheiro como texto (ADR 015) — tested by: frontend/src/dinheiro.test.ts::sem_float

## Notes

O design vem do usuário. Endereço padrão `http://abako.localhost:8080` (ADR 035). Sem lançamento offline. O service worker não cacheia respostas autenticadas da API.
