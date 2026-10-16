# Handoff para a skill visual-explainer

`guia-publish` não gera HTML diretamente — empacota o conteúdo consolidado e invoca a skill
`visual-explainer` (`.claude/skills/visual-explainer/SKILL.md`). Este arquivo mapeia cada seção
de um guia para o padrão visual correspondente daquela skill.

## Mapa seção do guia → padrão visual-explainer

| Seção do guia | Abordagem recomendada | Referência na visual-explainer |
|---|---|---|
| Título + objetivo final + glossário | Hero/intro em prosa com cards de glossário | "Prose Page Elements" em `references/css-patterns.md` |
| Navegação entre 4+ blocos | TOC lateral sticky | `references/responsive-nav.md` |
| Bloco de implementação (contexto/conceito/código) | CSS Grid cards, conteúdo rico | `templates/architecture.html` |
| Comandos/código | `pre`/`code` com syntax highlight manual | `references/css-patterns.md` |
| Tabela comparativa dentro de "Conceito" | HTML `<table>` semântica | `templates/data-table.html` |
| Fluxo com decisão (ex.: "qual ambiente usar") | Mermaid `flowchart TD` | `templates/mermaid-flowchart.html` |
| Critério de aceite | Lista de checkbox estilizada (`.card` com ícones de check) | `references/css-patterns.md` |
| Apêndice de comandos compilados | Tabela ou lista de código, agrupado por bloco de origem | `templates/data-table.html` |
| Apêndice de troubleshooting/FAQ | Cards de pergunta/resposta ou accordion simples em CSS | "Prose Page Elements" em `references/css-patterns.md` |

## Passos do handoff

1. Escolha **uma direção estética** (Blueprint, Editorial, Paper/ink, Monochrome terminal, ou
   IDE-inspired/Data-dense) — ver `references/aesthetics.md` da visual-explainer. Não default
   para "dark theme com azul" sem decidir.
2. Monte o esqueleto HTML com TOC lateral (se 4+ blocos) usando `references/responsive-nav.md`.
3. Para cada bloco do roteiro, renderize a anatomia contexto/conceito/implementação/verificação/
   critério de aceite como uma seção com heading `<h2>` numerado — mantenha a ordem do roteiro.
4. Rode os quality checks da visual-explainer (squint test, swap test, ambos os temas, sem
   overflow, informação completa) antes de considerar o HTML pronto.
5. Escreva o arquivo em `docs/guias/{slug}.html` (ou destino pedido pelo usuário) — não em
   `~/.agent/diagrams/` (esse caminho é para diagramas efêmeros da visual-explainer, não para
   o artefato final e versionável de um guia).

## O que NÃO fazer

- Não reimplementar CSS/JS de zero — os templates da visual-explainer já resolvem responsividade,
  temas claro/escuro e zoom de diagramas Mermaid.
- Não gerar um HTML por bloco — o guia é uma página única e navegável, não uma coleção de
  arquivos soltos.
- Não pular os quality checks porque "é só um guia" — um guia ilegível no celular ou sem tema
  escuro falha no mesmo padrão de qualidade que qualquer outro artefato da visual-explainer.
