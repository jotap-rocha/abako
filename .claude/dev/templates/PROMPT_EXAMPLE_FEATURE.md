# PROMPT: EXAMPLE_FEATURE

> Exemplo de PROMPT pro Dev Loop — construindo um utilitário Python

---

## Goal

Criar um utilitário de parsing de data que lida com múltiplos formatos e retorna ISO 8601.

---

## Quality Tier

**Tier:** production

---

## Context

- Local do arquivo: `src/utils/date_parser.py`
- Local do teste: `tests/test_date_parser.py`
- Deve suportar: ISO, formato US (MM/DD/YYYY), formato EU (DD/MM/YYYY)
- Python 3.11+ com type hints

---

## Tasks (Prioritized)

### 🔴 RISKY (Do First)

- [ ] Decidir biblioteca de parsing de data (dateutil vs manual): documentar decisão em Notes
- [ ] Criar estrutura de diretório se necessário: Verify: `mkdir -p src/utils tests`

### 🟡 CORE

- [ ] Criar `src/utils/__init__.py`: Verify: `ls src/utils/__init__.py`
- [ ] Implementar `date_parser.py` com função `parse_date()`
- [ ] Implementar lógica de detecção de formato: Verify: `python -c "from src.utils.date_parser import parse_date; print('Import OK')"`
- [ ] Criar testes abrangentes pra `date_parser`
- [ ] Rodar testes: Verify: `uv run pytest tests/test_date_parser.py -v`

### 🟢 POLISH (Do Last)

- [ ] Adicionar docstrings e type hints: Verify: `python -c "from src.utils.date_parser import parse_date; print(parse_date.__doc__)"`
- [ ] @revisor-codigo: Revisa a implementação em busca de caso de borda

---

## Exit Criteria

- [ ] Módulo importa com sucesso: `python -c "from src.utils.date_parser import parse_date; print('OK')"`
- [ ] Todos os testes passam: `uv run pytest tests/test_date_parser.py --tb=short`
- [ ] Type hints presentes: `grep -q "def parse_date.*->.*:" src/utils/date_parser.py && echo "OK"`
- [ ] Lida com formato ISO: `python -c "from src.utils.date_parser import parse_date; assert parse_date('2026-01-25') == '2026-01-25'"`
- [ ] Lida com formato US: `python -c "from src.utils.date_parser import parse_date; assert parse_date('01/25/2026') == '2026-01-25'"`

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
max_iterations: 20
max_retries: 3
circuit_breaker: 3
small_steps: true
feedback_loops:
  - uv run pytest tests/test_date_parser.py --tb=short
  - python -c "from src.utils.date_parser import parse_date"
```

---

## Notes

**Decision Log:**
- [ ] Escolha de biblioteca: [TBD — dateutil ou parsing manual?]

Este é um PROMPT de exemplo demonstrando como construir uma feature simples com o Dev Loop.
Copie este arquivo pra `.claude/dev/tasks/` e customize pro seu caso de uso.

---

## References

- [Boas práticas Python](.claude/rules/estilo-codigo.md)
- [PROMPT Template](.claude/dev/templates/PROMPT_TEMPLATE.md)
