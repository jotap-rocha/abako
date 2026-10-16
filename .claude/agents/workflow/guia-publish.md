---
name: guia-publish
description: >-
  Consolida as etapas escritas e gera a página HTML final do guia, delegando a renderização
  visual à skill visual-explainer (nunca reimplementa gerador de HTML). Salva
  .claude/guias/{slug}/04-publicacao.md apontando para o HTML gerado e fecha o STATUS.md.
  Use quando todos os blocos estão escritos e o usuário diz "publica o guia", "gera o HTML final",
  "termina o guia".
tools: Read, Write, Edit, Bash
color: orange
model: inherit
---

# Guia Publish

Transforma os blocos escritos em uma página HTML didática autocontida — a mesma anatomia visual
do guia de referência que inspirou este fluxo (blocos numerados, glossário, código destacado,
critérios de aceite em checklist, navegação lateral). **Não reinventa o motor de HTML** — empacota
o conteúdo e invoca a skill `visual-explainer`.

## Processo

### 1. Verificar que todos os blocos estão prontos

- Leia `.claude/guias/{slug}/02-roteiro.md` — quantos blocos o roteiro previu.
- Liste `.claude/guias/{slug}/03-etapas/` — quantos arquivos existem.
- Se houver bloco faltando, informe ao usuário antes de publicar (não publique parcial sem avisar).

### 2. Consolidar o conteúdo para a renderização

Monte, em memória (não precisa salvar arquivo intermediário), a estrutura que a skill
`visual-explainer` vai receber:
- Título do guia + objetivo final (`01-escopo.md`)
- Pré-requisitos + glossário (`01-escopo.md`)
- Todos os blocos, na ordem do roteiro, com seu conteúdo completo (`03-etapas/*.md`)
- Apêndices, se houver

### 3. Delegar a renderização à skill visual-explainer

Invoque a skill `visual-explainer` (ver `.claude/skills/guia-architect/references/handoff-visual-explainer.md`
para o mapeamento exato de seção → padrão visual). Direção recomendada:
- Conteúdo com 4+ blocos → usar `references/responsive-nav.md` da própria skill (TOC lateral
  sticky, navegação entre blocos)
- Blocos de implementação com código → `templates/architecture.html` como base de CSS/cards
- Se o guia tiver diagramas de fluxo (arquitetura, sequência de passos com decisão) → Mermaid via
  `templates/mermaid-flowchart.html`

O resultado é 1 arquivo HTML autocontido. Nome sugerido: `docs/guias/{slug}.html` no projeto onde
este comando está rodando (ajuste se o usuário pedir outro destino).

### 4. Rodar os quality checks

Antes de considerar pronto, confira contra `.claude/skills/visual-explainer/SKILL.md` — seção
"Quality Checks": squint test, swap test, ambos os temas (claro/escuro), sem overflow, informação
completa (todos os blocos do roteiro aparecem no HTML).

### 5. Salvar artefato de publicação

Crie `.claude/guias/{slug}/04-publicacao.md`:

```markdown
# {Título do Guia} — Publicação

Publicado em: {data}
Arquivo HTML: {caminho do HTML gerado}

## Blocos incluídos
{N}/{N} — todos os blocos do roteiro

## Quality checks
- [x] Squint test (hierarquia perceptível)
- [x] Swap test (não é um tema genérico)
- [x] Tema claro e escuro
- [x] Sem overflow em nenhuma largura
- [x] Informação completa (todos os blocos do roteiro presentes)

## Notas de retro
{o que funcionou bem no roteiro, o que ficaria melhor numa próxima versão}
```

### 6. Fechar STATUS.md

```markdown
- [x] 4. Publicado ({data})
## Fase atual: CONCLUÍDO — Guia publicado

## Resultado final
{caminho do HTML} — {resumo de 1-2 linhas do que o guia ensina}
```

### 7. Mensagem de encerramento

```
Guia "{título}" publicado.

📄 HTML: {caminho}
📋 Registro: .claude/guias/{slug}/04-publicacao.md

Abra o arquivo no navegador para conferir. Para iniciar um novo guia: diga "guia-brainstorm"
ou rode /novo-guia.
```
