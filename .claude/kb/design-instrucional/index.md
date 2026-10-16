---
domain: design-instrucional
description: Metodologia de design instrucional para guias passo-a-passo técnicos — sequenciamento pedagógico, estrutura de bloco uniforme, público-alvo, glossário antes de código
mcp_validated: null
confidence: null
---

# KB: Design Instrucional — Guias Passo-a-Passo

Base de conhecimento sobre **como estruturar um tutorial técnico hands-on**, não sobre uma
tecnologia específica. É a metodologia que os agents `guia-roteiro` e `guia-etapas` (fluxo
`/novo-guia`) consultam para decidir a ordem dos blocos e o formato de cada etapa — o
conhecimento técnico do assunto em si (Databricks, Kubernetes, etc.) vem de outros domínios KB
ou do material-fonte que o usuário fornecer.

## Capability map

| Pergunta | Onde achar a resposta |
|---|---|
| Em que ordem os blocos de um guia devem aparecer? | [concepts/sequenciamento-pedagogico.md](concepts/sequenciamento-pedagogico.md) |
| Como escrever um bloco de implementação de forma consistente? | [concepts/estrutura-de-prompt-uniforme.md](concepts/estrutura-de-prompt-uniforme.md) |
| Como decidir pré-requisitos e nível do leitor? | [concepts/publico-alvo-e-pre-requisitos.md](concepts/publico-alvo-e-pre-requisitos.md) |
| Por que o glossário vem antes do código? | [concepts/glossario-antes-do-codigo.md](concepts/glossario-antes-do-codigo.md) |
| Qual o template de bloco (contexto/conceito/código/validação)? | [patterns/bloco-contexto-conceito-codigo-validacao.md](patterns/bloco-contexto-conceito-codigo-validacao.md) |
| Como fechar um guia com checklist de produção? | [patterns/checklist-de-producao.md](patterns/checklist-de-producao.md) |
| Como estruturar um apêndice de troubleshooting? | [patterns/apendice-de-troubleshooting.md](patterns/apendice-de-troubleshooting.md) |

## Conceitos

| Arquivo | Tópico |
|---|---|
| [sequenciamento-pedagogico.md](concepts/sequenciamento-pedagogico.md) | Ordem contextualização → preparação → implementação → validação |
| [estrutura-de-prompt-uniforme.md](concepts/estrutura-de-prompt-uniforme.md) | Por que cada bloco segue a mesma anatomia, e o que isso economiza de carga cognitiva |
| [publico-alvo-e-pre-requisitos.md](concepts/publico-alvo-e-pre-requisitos.md) | Como declarar nível do leitor e pré-requisitos sem inflar ou reduzir escopo |
| [glossario-antes-do-codigo.md](concepts/glossario-antes-do-codigo.md) | Por que termos técnicos precisam de definição centralizada antes de aparecerem em comandos |

## Padrões

| Arquivo | Tópico |
|---|---|
| [bloco-contexto-conceito-codigo-validacao.md](patterns/bloco-contexto-conceito-codigo-validacao.md) | O template de bloco usado por `guia-etapas` |
| [checklist-de-producao.md](patterns/checklist-de-producao.md) | Checklist final antes de considerar um guia "pronto" |
| [apendice-de-troubleshooting.md](patterns/apendice-de-troubleshooting.md) | Como consolidar pegadinhas espalhadas pelos blocos num apêndice único |

## Learning path

1. Comece por `concepts/publico-alvo-e-pre-requisitos.md` — sem saber quem é o leitor, nenhuma
   outra decisão de sequenciamento faz sentido.
2. Leia `concepts/sequenciamento-pedagogico.md` para a ordem macro dos blocos.
3. `concepts/glossario-antes-do-codigo.md` e `concepts/estrutura-de-prompt-uniforme.md` cobrem as
   duas regras que mais previnem confusão no leitor.
4. Os 3 arquivos de `patterns/` são receitas operacionais — leia sob demanda, não em sequência.

## Quick Reference

Ver [quick-reference.md](quick-reference.md) — checklist condensado, ler só se a tarefa exigir
esse nível de detalhe (ex.: revisão rápida de um roteiro já pronto).

## Nota de validação

Este domínio não é sobre uma biblioteca/tecnologia externa — é metodologia de design instrucional
derivada de um formato de guia de referência (aula ao vivo hands-on) e dos princípios já usados
pelo fluxo `/novo-projeto` deste canônico. `mcp_validated` e `confidence` ficam `null` porque não
há documentação oficial de terceiros para validar via Context-7 — mesma convenção já usada em
domínios sem MCP disponível (`lakehouse`, `rag`) neste repositório.
