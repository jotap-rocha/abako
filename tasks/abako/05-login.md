# SPEC-002: login e sessão

**Status:** not started  
**Blocked by:** tasks/abako/03-esquema-base.md

## What to build

Login com senha (Argon2id), sessão no servidor, logout, comando local para criar usuário e recuperar senha, rate limit, CSRF, CORS com origens explícitas, validação de `Host`. Toda consulta usa o `user_id` da sessão.

## Acceptance criteria

- [ ] SPEC-002-AC-1: senha errada é rejeitada e excesso de tentativas é limitado — tested by: tests/backend/test_login.py::test_rate_limit
- [ ] SPEC-002-AC-2: um usuário nunca enxerga dados de outro (INV-13) — tested by: tests/backend/test_isolamento.py::test_acesso_cruzado_negado
- [ ] SPEC-002-AC-3: `abako.localhost`, `localhost` e `127.0.0.1` são aceitos como Host e qualquer outro é rejeitado (INV-34, ADR 035) — tested by: tests/backend/test_host.py::test_host_permitido_e_invalido
- [ ] SPEC-002-AC-4: escrita sem token CSRF ou com Origin inválida é rejeitada — tested by: tests/backend/test_csrf.py::test_csrf_e_origin
- [ ] SPEC-002-AC-5: senha e sessão nunca aparecem em log — tested by: tests/backend/test_logs.py::test_sem_segredo_em_log

## Notes

Cabeçalhos `Cache-Control: no-store` e CSP (ADR 031).
