# PROMPT: [NOME]

> Substitua [NOME] pelo identificador da task (ex.: REDIS_KB, DATE_PARSER, CACHE_FEATURE)

---

## Goal

[Uma frase descrevendo o estado "pronto" — específico e verificável]

---

## Quality Tier

<!-- Escolha UM tier que define a expectativa desta task -->

**Tier:** production

| Tier | Expectativa |
|---|---|
| `prototype` | Velocidade acima de perfeição. Pula caso de borda. Teste mínimo. |
| `production` | Testes obrigatórios. Boas práticas. Verificação completa. |
| `library` | Compatibilidade retroativa. Documentação completa. API estável. |

---

## Context

[Opcional: background, restrições, referência de arquivo, ou link pra código/doc existente]

---

## Tasks (Prioritized)

<!--
Ordem de prioridade: execute RISKY primeiro, depois CORE, depois POLISH
Marque com: - [ ] (pendente) ou - [x] (feito)
Use @nome-do-agente pra invocar um agente específico
Adicione verificação com: Verify: `comando`
-->

### 🔴 RISKY (Do First)
<!-- Decisão arquitetural, incerteza, ponto de integração -->

- [ ] [Task arquitetural ou de integração]

### 🟡 CORE
<!-- Implementação principal da feature -->

- [ ] [Task principal]
- [ ] @nome-do-agente: [Task que precisa de um agente específico]
- [ ] [Task com verificação]: Verify: `uv run pytest tests/test_foo.py`

### 🟢 POLISH (Do Last)
<!-- Limpeza, otimização, nice-to-have -->

- [ ] [Task de limpeza ou otimização]

---

## Exit Criteria

<!--
Liste condições OBJETIVAS e VERIFICÁVEIS que indicam conclusão.
Cada critério deve ser checável com um comando.
-->

- [ ] Todos os testes passam: `uv run pytest --tb=short`
- [ ] Types conferem: `uv run mypy .`
- [ ] Lint passa: `uv run ruff check .`
- [ ] Arquivo existe: `ls path/do/arquivo/esperado`
- [ ] [Critério customizado]: `[comando de verificação]`

---

## Progress

<!--
AUTO-ATUALIZADO pelo executor após cada iteração.
Este é o "memory bridge" que evita gasto de token com re-exploração.
-->

**Status:** NOT_STARTED

| Iteration | Timestamp | Task Completed | Key Decision | Files Changed |
|---|---|---|---|---|
| - | - | - | - | - |

---

## Config

```yaml
mode: hitl                # hitl (human-in-loop) | afk (autônomo)
quality_tier: production  # prototype | production | library
max_iterations: 30        # para após N loops
max_retries: 3            # tenta de novo task que falhou N vezes
circuit_breaker: 3        # para se não houver progresso por N loops
small_steps: true         # uma mudança lógica por task
feedback_loops:           # comandos a rodar entre tasks
  - uv run pytest
  - uv run mypy .
  - uv run ruff check .
```

---

## Notes

[Opcional: notas adicionais, lembretes, decisões arquiteturais, ou TODOs]

---

## References

<!-- Links pra documentação relevante, PRDs, ou recursos externos -->

- [PRD ou spec relacionado](.claude/sdd/features/PRD_*.md)
- [Documentação externa](https://...)
