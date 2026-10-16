---
topic: bloco-contexto-conceito-codigo-validacao
confidence: null
mcp_validated: null
---

# Padrão: Bloco Contexto → Conceito → Código → Validação

Receita operacional usada por `guia-etapas` para escrever cada bloco de implementação. Ver
também `.claude/skills/guia-architect/references/template-etapa.md` para o template completo
com exemplo preenchido — este arquivo foca no *quando aplicar cada variação*.

## Receita padrão

```markdown
# Bloco {N} — {Título}

## Contexto
{1 parágrafo curto}

## Conceito
{explicação do porquê, com tabela/diagrama se ajudar}

## Implementação
{comando/código comentado + pegadinhas}

## Verificação
{sinal concreto de sucesso}

## Critério de aceite
- [ ] {testável}
```

## Variações válidas

**Bloco de contextualização** (não tem comando):
```markdown
## Contexto
## Conceito
## Critério de aceite   ← "li e entendi o objetivo do guia" não é testável;
                          use "consigo explicar em uma frase o que vou construir"
```

**Bloco de apêndice/FAQ** (não segue a ordem linear):
```markdown
## Pergunta
## Resposta
## Ver também   ← link para o bloco principal relacionado, se houver
```

**Bloco com mais de um caminho válido** (ex.: dois SOs, dois provedores):
```markdown
## Implementação
### Opção A — {contexto em que essa opção se aplica}
{comando}
### Opção B — {contexto em que essa opção se aplica}
{comando}
```
Nunca apresente as opções sem dizer quando cada uma se aplica — isso empurra a decisão de volta
para o leitor sem informação suficiente.

## Quando NÃO usar este padrão

Blocos puramente informativos que não fazem parte da progressão do guia (ex.: "sobre o autor",
"changelog do guia") não precisam da anatomia — são metadado, não conteúdo pedagógico.
