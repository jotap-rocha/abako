# Template MADR — corpo do arquivo ADR

Ler ao executar o Passo 3 do SKILL.md (criar o arquivo). Caminho: `docs/adr/NNN-titulo-em-kebab-case.md`.

```markdown
# NNN — {Título da Decisão}

**Status:** Aceita  
**Data:** {YYYY-MM-DD}  
**Autores:** {nomes ou "time"}

---

## Contexto

{Por que essa decisão precisou ser tomada? Qual o problema que motivou isso?
Quais forças/restrições estavam em jogo? Ser específico — evitar linguagem genérica.}

## Decisão

{O que foi decidido? Formulado como frase afirmativa:
"Vamos usar X porque Y."}

## Alternativas consideradas

### Opção A — {nome} ❌ Rejeitada
{Descreva brevemente. Por que foi rejeitada?}

### Opção B — {nome} ✅ Escolhida
{Descreva brevemente. Por que foi escolhida?}

### Opção C — {nome} ❌ Rejeitada (se houver)
{Descreva brevemente.}

## Consequências

### Positivas
- {benefício 1}
- {benefício 2}

### Negativas / Tradeoffs
- {custo ou limitação 1}
- {custo ou limitação 2}

### Riscos
- {risco que a decisão introduz, se houver}

## Revisão

Esta ADR deve ser revisada se:
- {condição 1 — ex: volume de dados ultrapassar X}
- {condição 2 — ex: surgir biblioteca Y com suporte a Z}
```

## Índice — `docs/adr/README.md`

Se não existir, criar:

```markdown
# Architecture Decision Records

Registro de decisões arquiteturais significativas deste projeto.

## Decisões

| # | Título | Status | Data |
|---|---|---|---|
| [001](001-titulo.md) | Título | Aceita | 2026-06-27 |
```

Se já existir, adicionar a nova linha na tabela.
