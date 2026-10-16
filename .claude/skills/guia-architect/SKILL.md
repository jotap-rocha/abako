---
name: guia-architect
description: >-
  Princípios de design didático para guias passo-a-passo de implementação (qualquer assunto
  técnico): como quebrar em blocos, escrever o template uniforme de etapa, decidir quando puxar
  KB técnico, e empacotar o conteúdo final para a skill visual-explainer renderizar. Use quando
  os agents guia-roteiro/guia-etapas/guia-publish precisarem da metodologia completa, ou quando
  o usuário pedir para revisar/ajustar a estrutura pedagógica de um guia já em andamento.
---

# Guia Architect

Documenta os princípios de design instrucional que o fluxo `/novo-guia` aplica (agents
`guia-brainstorm` → `guia-escopo` → `guia-roteiro` → `guia-etapas` → `guia-publish`). Esta skill
não conduz o fluxo sozinha — os agents fazem isso — ela é a referência que eles consultam para
decisões de estrutura.

## Princípios que guiam a condução

- **Conceito antes de código, sempre.** Nenhum bloco de implementação começa com um comando sem
  explicar o que ele faz e por quê agora. Ver `references/checklist-didatico.md`.
- **Resultado observável a cada etapa.** O leitor nunca avança dois blocos sem confirmar que o
  anterior funcionou — número esperado, print, comando de teste.
- **Glossário precede o domínio.** Termos técnicos são definidos antes de aparecerem em código,
  não explicados inline no meio de um comando.
- **Critério de aceite é sempre testável, nunca vago.** "Funciona" não é critério; "o comando X
  retorna N linhas" é.
- **KB técnico é matéria-prima, não cópia.** Quando o assunto do guia bate com um domínio já
  coberto em `.claude/kb/`, o roteiro se inspira no conteúdo — não copia ao pé da letra, porque o
  KB é referência operacional, o guia é narrativa pedagógica.
- **Não reinventar o motor de renderização.** A saída visual (HTML autocontido, blocos numerados,
  navegação lateral) já existe na skill `visual-explainer` — `guia-publish` empacota conteúdo e
  delega. Ver `references/handoff-visual-explainer.md`.
- **Comece mínimo.** Nem todo guia precisa de apêndices de troubleshooting ou 20 blocos — o número
  de blocos segue o escopo real definido em `01-escopo.md`, nunca um template fixo.

## Referências

- `references/template-etapa.md` — o template uniforme de bloco (contexto → conceito → código →
  verificação → critério de aceite), com exemplos preenchidos e vazios lado a lado.
- `references/checklist-didatico.md` — regras de sequenciamento pedagógico: o que precisa vir
  antes de quê, e como detectar quando um bloco está tentando ensinar coisa demais de uma vez.
- `references/handoff-visual-explainer.md` — como mapear seções do guia (glossário, blocos,
  apêndices) para os templates/padrões da skill `visual-explainer`.

## Quando usar KB vs esta skill

- **`.claude/kb/design-instrucional/`** — conceitos e padrões reutilizáveis de design
  instrucional, consumidos JIT (arquivo específico, não o domínio inteiro) pelo `guia-roteiro`
  e `guia-etapas`.
- **Esta skill (`guia-architect`)** — os princípios de mais alto nível e o processo de decisão;
  leia quando for ajustar a estrutura de um guia inteiro, não um bloco isolado.

## Lembretes ao conduzir

- Não pergunte ao usuário o que já está em `00-tema.md`/`01-escopo.md` — infira e confirme.
- Prefira o menor número de blocos que cobre o objetivo final declarado em `01-escopo.md`.
- Todo bloco de implementação sem teste/verificação mapeável precisa registrar explicitamente
  por que não há verificação — nunca omita silenciosamente.
