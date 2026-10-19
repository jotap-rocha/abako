# 031 — Segurança local da API e PWA online

**Status:** Aceita
**Data:** 2026-10-19
**Autores:** time
**Reversibilidade:** moderada

---

## Contexto

"Local-first" não é modelo de segurança: página externa pode tentar chamar a API em `127.0.0.1`, e a PWA pode manter dados em cache.

## Decisão

- Validação do cabeçalho `Host` (contra DNS rebinding); CORS com origens explícitas (ADR 020).
- Limpar o cache financeiro da PWA no logout.
- A senha **não protege** contra outra pessoa com acesso à mesma conta do Windows; limite documentado.
- PWA **instalável, usada no navegador do mesmo PC** (`127.0.0.1`), online; sem lançamento offline na v1.
- Respostas financeiras com `Cache-Control: no-store`; CSP restritiva; o service worker **não cacheia** respostas autenticadas da API.
- **Acesso futuro** por celular, rede local ou rede externa é pretendido, mas está **fora da v1** e viola a regra de escuta só em `127.0.0.1`: exige ADR próprio (TLS, exposição, autenticação reforçada, rate limit) antes de qualquer mudança.
- Complementa o ADR 020 (Host/CORS/CSRF).

## Alternativas consideradas

Offline com sincronização ❌ (conflito com o SCD2).

## Como verificar

INV-34; testes de Host, CORS e logout (SPEC-002, SPEC-012).

## Impacto em SI/LGPD

Reforça a proteção de dados financeiros; sem dado novo.
