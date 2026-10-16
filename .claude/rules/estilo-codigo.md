---
# Estilo de código — carrega ao tocar arquivos Python.
paths:
  - "**/*.py"
---

# Estilo de código (Python)

Padrão de estilo do time. O hook de `PostToolUse` já roda `ruff format` + `ruff check --fix`
a cada edição — escreva código que **passa limpo** sem depender do autofix.

- **Formatação/lint:** `ruff` (config em `pyproject.toml`). `line-length = 100`, alvo `py313`.
- **Tipagem:** `mypy`. Toda função pública tem type hints completos.
  Evite `Any`; quando inevitável, comente o porquê. Prefira `X | None` a `Optional[X]`.
- **`from __future__ import annotations`** no topo de cada módulo (anotações como string).
- **Docstrings curtas** explicando o *porquê*, não o *o quê*. Uma linha quando possível.
- **Nomes do domínio no idioma do projeto** — use o glossário em `CONTEXT.md`. Não traduza o
  domínio para inglês no meio do código se ele está em português (e vice-versa).
- **Sem `print`** em código de runtime — use `logging` estruturado. `print` só em scripts de
  seed/ingestion ou CLIs.
- **Funções pequenas e puras** onde der; efeito colateral (I/O, rede, DB) isolado e explícito.
- **Sem segredo hardcoded** — tudo via settings (pydantic-settings lê do `.env`).
- **SOLID:** cada classe tem uma responsabilidade; dependa de abstrações, não de concreto.
  Para pipelines de dados, consulte `rules/pipeline.md`.
