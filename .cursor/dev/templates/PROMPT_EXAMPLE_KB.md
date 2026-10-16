# PROMPT: EXAMPLE_KB

> Exemplo de PROMPT pro Dev Loop — construindo uma Knowledge Base

---

## Goal

Criar um domínio de KB completo de Redis com quick-reference, concepts e patterns, seguindo o
padrão de arquitetura de KB deste harness.

---

## Quality Tier

**Tier:** production

---

## Context

- Domínios de KB vivem em `.claude/kb/{domain}/`
- Deve seguir a estrutura: `index.md`, `quick-reference.md`, `concepts/`, `patterns/`
- Registro fica em `.claude/kb/_index.yaml`
- Ver KB existente pra referência de formato: `.claude/kb/dbt/`

---

## Tasks (Prioritized)

### 🔴 RISKY (Do First)

- [ ] Validar requisito de estrutura de KB lendo `.claude/kb/_index.yaml`
- [ ] Checar se o domínio Redis já existe: Verify: `ls .claude/kb/redis/ 2>/dev/null || echo "Domain not found"`

### 🟡 CORE

- [ ] @kb-architect: Cria a estrutura do domínio KB de Redis
- [ ] Criar `quick-reference.md` (máx 100 linhas): Verify: `wc -l .claude/kb/redis/quick-reference.md | awk '{print ($1 <= 100) ? "OK" : "TOO_LONG"}'`
- [ ] Criar `concepts/data-structures.md`: Verify: `ls .claude/kb/redis/concepts/data-structures.md`
- [ ] Criar `concepts/persistence.md`: Verify: `ls .claude/kb/redis/concepts/persistence.md`
- [ ] Criar `patterns/caching.md`: Verify: `ls .claude/kb/redis/patterns/caching.md`

### 🟢 POLISH (Do Last)

- [ ] Atualizar `.claude/kb/_index.yaml` com o domínio Redis
- [ ] @revisor-codigo: Revisa a estrutura da KB em busca de completude

---

## Exit Criteria

- [ ] Pasta do domínio existe: `ls -la .claude/kb/redis/`
- [ ] Quick reference existe: `ls .claude/kb/redis/quick-reference.md`
- [ ] Ao menos 2 concepts: `ls .claude/kb/redis/concepts/ | wc -l | awk '{print ($1 >= 2) ? "OK" : "NEED_MORE"}'`
- [ ] Ao menos 1 pattern: `ls .claude/kb/redis/patterns/ | wc -l | awk '{print ($1 >= 1) ? "OK" : "NEED_MORE"}'`
- [ ] Registrado no índice: `grep -q "redis" .claude/kb/_index.yaml && echo "OK" || echo "NOT_REGISTERED"`

---

## Progress

**Status:** NOT_STARTED

| Iteration | Timestamp | Task Completed | Key Decision | Files Changed |
|---|---|---|---|---|
| - | - | - | - | - |

---

## Config

```yaml
mode: hitl
quality_tier: production
max_iterations: 15
max_retries: 3
circuit_breaker: 3
small_steps: true
feedback_loops:
  - ls .claude/kb/redis/
```

---

## Notes

Este é um PROMPT de exemplo demonstrando como construir um domínio de KB com o Dev Loop.
Copie este arquivo pra `.claude/dev/tasks/` e customize pro seu caso de uso. Para um domínio de
KB de verdade, considere usar `kb-architect` diretamente (`.claude/agents/architect/`) ou o
comando correspondente — o Dev Loop aqui é só mais uma forma de disparar o mesmo agente dentro
de um fluxo com verificação e recovery.

---

## References

- [Arquitetura de KB](.claude/kb/_index.yaml)
- [Exemplo de KB existente](.claude/kb/dbt/)
