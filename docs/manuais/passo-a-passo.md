# GUIA-PASSO-A-PASSO — criando tutoriais didáticos com `/novo-guia`

> Conceito complementar ao fluxo principal do harness (`/novo-projeto` → `harness-*`).
> Serve para criar um **tutorial hands-on** (passagem de conhecimento) sobre qualquer assunto
> técnico — não um projeto de código. Detalhe técnico completo em `.claude/guias/README.md` e
> nos agentes `.claude/agents/workflow/guia-*.md` — este arquivo é a introdução e o guia de uso.

---

## O que é

Um formato de tutorial no espírito de um guia de aula ao vivo: blocos numerados, conceito sempre
antes do código, glossário definido antes de aparecer em comando, e resultado observável a cada
etapa. A saída final é **uma página HTML autocontida**, pronta para abrir no navegador e navegar
entre os blocos.

Funciona para qualquer assunto — configurar uma ferramenta, migrar de A para B, ensinar um
conceito com um exemplo mínimo, ou explicar como um projeto inteiro funciona para quem está
entrando agora.

## Passo a passo

### 1. Inicie o fluxo

```
/novo-guia
```

O agente `guia-brainstorm` pergunta o assunto, se você tem um material de referência (link/doc
de inspiração ou do zero), o tipo de guia e quem é o leitor. Cria
`.claude/guias/{slug}/00-tema.md`.

### 2. Defina o escopo

```
guia-escopo
```

Estrutura o objetivo final (o que o leitor consegue fazer ao terminar), pré-requisitos,
glossário de termos e a jornada macro. Salva em `01-escopo.md`.

### 3. Desenhe o roteiro

```
guia-roteiro
```

Quebra o guia em blocos numerados: contextualização → preparação → implementação (N blocos) →
validação/produção → apêndices. Se o assunto bate com um domínio já coberto em `.claude/kb/`
(ex.: Databricks, Airflow), o agente reaproveita esse conhecimento técnico sob demanda. Salva em
`02-roteiro.md`.

### 4. Escreva as etapas

```
guia-etapas
```

Escreve o conteúdo de cada bloco, sempre na mesma ordem: **contexto → conceito → código/comando
→ verificação → critério de aceite**. Um arquivo por bloco em `03-etapas/`. Pode ser chamado
várias vezes ("próximo bloco") até todos os blocos do roteiro terem conteúdo.

### 5. Publique o HTML final

```
guia-publish
```

Consolida tudo e gera a página HTML final (delega a renderização à skill `visual-explainer` —
navegação lateral, código destacado, tema claro/escuro). Salva o caminho do HTML em
`04-publicacao.md` e fecha o `STATUS.md` do guia.

## Exemplo rápido

```
/novo-guia
> Assunto: "Configurar CI/CD com GitHub Actions para um monorepo Node"
> Material-fonte: nenhum, vou descrever do zero
> Tipo: implementação técnica
> Público: dev pleno que nunca usou GitHub Actions

guia-escopo     → objetivo, pré-requisitos, glossário (workflow, runner, secret, matrix build...)
guia-roteiro    → 6 blocos: contexto → instalar CLI → 1º workflow → cache → matrix → validação
guia-etapas     → escreve os 6 blocos, um de cada vez
guia-publish    → docs/guias/cicd-github-actions-monorepo-node.html
```

## Se o escopo mudar no meio do caminho

```
guia-iterate
```

Atualiza o artefato certo (tema, escopo, roteiro ou etapa) e propaga a cascata para os
subsequentes — nunca descarta o que já foi escrito.

## Onde tudo fica

```
.claude/guias/{slug}/
├── STATUS.md          ← fase atual + checklist
├── 00-tema.md
├── 01-escopo.md
├── 02-roteiro.md
├── 03-etapas/
│   └── NN-{bloco}.md
└── 04-publicacao.md   ← aponta para o HTML final
```

## Retomando um guia em andamento

```bash
cat .claude/guias/{slug}/STATUS.md
```

| Fase | Próximo passo |
|---|---|
| 0 — Tema capturado | `guia-escopo` |
| 1 — Escopo definido | `guia-roteiro` |
| 2 — Roteiro desenhado | `guia-etapas` |
| 3 — Etapas escritas | `guia-publish` |
| 4 — Publicado | — |

---

## Referências

- `.claude/guias/README.md` — estrutura de pasta completa e tabela de fases
- `.claude/skills/guia-architect/SKILL.md` — princípios de design didático (sequenciamento,
  template de bloco, handoff para a `visual-explainer`)
- `.claude/kb/design-instrucional/` — metodologia consultada por `guia-roteiro`/`guia-etapas`
- `.claude/agents/workflow/guia-*.md` — os 6 agentes do fluxo
- `.claude/commands/novo-guia.md` — definição do comando `/novo-guia`
