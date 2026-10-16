---
name: new-adr
description: >-
  Registra uma Architecture Decision Record (ADR) em docs/adr/ com template padronizado.
  Cria o arquivo numerado, preenche contexto/decisão/consequências e atualiza o índice.
  Use quando: "registra essa decisão", "cria um ADR para isso", "documenta a escolha de
  tecnologia", "por que escolhemos X em vez de Y?", "ADR para esse tradeoff", "/new-adr".
---

# New ADR

Cria e registra uma Architecture Decision Record seguindo o formato MADR (Markdown ADR).

## Quick start

```
/new-adr
```

## Processo

### Passo 1 — Coletar informações (4 perguntas)

1. **Qual a decisão tomada?** (ex: "usar LangGraph em vez de ReAct livre")
2. **Qual o contexto?** (por que essa decisão precisou ser tomada?)
3. **Quais alternativas foram consideradas?** (pelo menos 2)
4. **Quais são as consequências positivas e negativas?**

### Passo 2 — Numerar o ADR

```bash
# Descobrir o próximo número
ls docs/adr/*.md 2>/dev/null | grep -oP '\d+' | sort -n | tail -1
```
Se não houver ADRs, começa em `001`.

### Passo 3 — Criar o arquivo

Caminho: `docs/adr/NNN-titulo-em-kebab-case.md`. Ver `references/adr-template.md` para o template
MADR completo (Contexto, Decisão, Alternativas, Consequências, Revisão).

### Passo 4 — Atualizar o índice

Ver `references/adr-template.md` (seção "Índice") para o template de `docs/adr/README.md`.
Se já existir, só adicionar a nova linha na tabela.

### Passo 5 — Confirmar

Exibir o arquivo criado e o índice atualizado antes de salvar.
Perguntar se há ajustes antes de fechar.

## Status possíveis

| Status | Significado |
|---|---|
| `Proposta` | Em discussão, não implementada |
| `Aceita` | Decisão tomada e implementada |
| `Substituída por [NNN]` | Revogada por decisão posterior |
| `Obsoleta` | Não se aplica mais, mas mantida para histórico |

## Quando criar um ADR

Criar ADR sempre que:
- Escolher uma tecnologia ou biblioteca entre alternativas
- Definir uma convenção arquitetural que o time deve seguir
- Tomar decisão com tradeoffs significativos
- Decidir algo que causaria surpresa se descoberto sem contexto

**Não criar ADR para:**
- Decisões triviais sem alternativas reais
- Escolhas de implementação de detalhe (nome de variável, etc.)
- Padrões já documentados em regras (`rules/`) — ADR é para o "porquê", não o "como"

## Referências

- `docs/adr/` — diretório de ADRs do projeto
- `.claude/skills/grill-with-docs/SKILL.md` — sessão de refinamento que gera ADRs inline
