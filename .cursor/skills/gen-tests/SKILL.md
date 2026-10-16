---
name: gen-tests
description: >-
  Gera testes automatizados (pytest ou vitest) para um módulo, função ou componente.
  Cria fixtures reutilizáveis, casos felizes, casos de borda e mocks cirúrgicos.
  Nunca mocka o que pode ser testado real. Use quando: "escreve testes para isso",
  "adiciona cobertura nesse módulo", "preciso de testes para esse serviço", "gera
  pytest para essa função", "testa esse componente React", "/gen-tests".
---

# Gen Tests

Gera testes automatizados com estrutura padronizada e fixtures reutilizáveis.

## Quick start

```
/gen-tests
```

## Processo

### Passo 1 — Identificar contexto

1. Ler o módulo/componente alvo
2. Identificar o framework: `pytest` (Python) ou `vitest` (TypeScript/React)
3. Listar as funções/métodos públicos a testar
4. Identificar dependências externas (DB, LLM, API) que precisam de mock

### Passo 2 — Decisão: mock vs real

| Dependência | Mockar? | Razão |
|---|---|---|
| Função pura (sem I/O) | ❌ Nunca | Testar direto |
| DB (em teste de unidade) | ✅ Sim | Isolar unidade |
| DB (em teste de integração) | ❌ Real | Detectar divergências |
| LLM externo | ✅ Sim | Caro, lento, não-determinístico |
| HTTP externo (Stripe, etc.) | ✅ Sim | Não disponível em CI |
| Qdrant (unidade) | ✅ Sim | Isolamento |

### Passo 3 — Gerar os testes

Ver `references/test-templates.md` para os templates completos (pytest com fixtures/casos
felizes/casos de borda, vitest + Testing Library, e `conftest.py` para fixtures compartilhadas).
Seguir a mesma estrutura: fixtures → casos felizes → casos de borda.

### Passo 4 — Verificar cobertura

```bash
# Python
uv run pytest --cov=app --cov-report=term-missing tests/

# TypeScript
npx vitest run --coverage
```

## Checklist de qualidade de testes

- [ ] Cada teste testa UMA coisa — sem múltiplos asserts não relacionados
- [ ] Nome do teste descreve o comportamento: `test_{quando}_{espera}`
- [ ] Fixtures no `conftest.py` para reuso entre arquivos
- [ ] Mocks apenas para I/O externo — não mockar o que pode ser testado real
- [ ] Testes de borda: input vazio, None, valor fora do range, erro de dependência
- [ ] Integração com DB real em `tests/integration/` separada dos testes de unidade

## Referências

- `.claude/kb/testing/` — padrões de teste por tipo
- `.claude/rules/testes.md` — invariantes de teste do projeto
