---
topic: glossario-antes-do-codigo
confidence: null
mcp_validated: null
---

# Glossário Antes do Código

Regra simples com efeito desproporcional: todo termo técnico específico do domínio precisa
aparecer no glossário (`01-escopo.md`) antes de aparecer em qualquer comando ou trecho de código
do guia.

## O problema que isso evita

Sem glossário centralizado, cada bloco que introduz um termo novo tem duas opções ruins: (a)
explicar inline, quebrando o ritmo do bloco de implementação com uma definição no meio do
"Conceito"; ou (b) não explicar, assumindo que o leitor infere pelo contexto — o que funciona até
não funcionar, e o leitor trava sem saber que termo pesquisar.

## Onde o glossário vive

- Estruturado em `01-escopo.md`, seção "Glossário", como tabela: termo, definição de 1-2 linhas,
  por que importa neste guia especificamente (não uma definição genérica de dicionário).
- Na publicação final (HTML), aparece na seção de contextualização/introdução, antes do primeiro
  bloco de implementação — nunca disperso pelo meio do guia.

## Como decidir o que entra no glossário

Entra: qualquer termo que (a) não é de conhecimento geral da área declarada como pré-requisito, e
(b) aparece em pelo menos um comando, nome de recurso, ou decisão técnica do guia.

Não entra: termos genéricos que qualquer leitor com o pré-requisito declarado já conhece (ex.:
não defina "variável de ambiente" num guia que já assume conhecimento básico de shell).

## Relação com "por que os termos importam"

O guia de referência que inspirou este fluxo não só lista termos — explica por que cada termo
importa *para este guia específico*, não a definição enciclopédica. Isso ajuda o leitor a saber
quanto esforço mental alocar para cada termo: um termo que só aparece uma vez de passagem pesa
menos que um que é usado em 5 blocos diferentes.

## Gotcha

Termos que mudam de significado entre o domínio geral e o contexto específico do guia (ex.: uma
palavra que tem um sentido comum na indústria mas um sentido mais estreito dentro de uma
ferramenta específica) são as maiores fontes de confusão silenciosa — priorize essas no
glossário mesmo que pareçam "óbvias".
