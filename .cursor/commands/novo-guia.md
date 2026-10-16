---
description: >-
  Inicia o fluxo guiado de criação de guia passo-a-passo didático (qualquer assunto técnico).
  Captura tema, público-alvo e material-fonte, cria .claude/guias/{slug}/ com STATUS.md e
  00-tema.md. Termina com uma página HTML autocontida no espírito de um guia hands-on de aula
  ao vivo — conceito antes de código, resultado observável a cada etapa.
---

# /novo-guia — fluxo guiado de guia passo-a-passo

Este comando inicia o `guia-brainstorm` para capturar o tema do guia e conduzir o fluxo até a
página HTML final.

---

## O que acontece

```
/novo-guia
    ↓
guia-brainstorm (agente)
    ├── Passo 1: "Sobre que assunto você quer criar um guia passo-a-passo?"
    ├── Passo 2: material-fonte (link/doc de inspiração, ou do zero)
    ├── Passo 3: tipo de guia (implementação / conceitual+prático / migração / onboarding / outro)
    ├── Passo 4: público-alvo (primeira leitura)
    ├── Deriva slug do tema
    └── Cria .claude/guias/{slug}/STATUS.md + 00-tema.md
```

---

## Fluxo completo pós-/novo-guia

```
1. /novo-guia          → 00-tema.md criado
2. guia-escopo          → objetivos, pré-requisitos, glossário, jornada → 01-escopo.md
3. guia-roteiro         → quebra em blocos (contextualização/prep/implementação/validação/apêndices) → 02-roteiro.md
4. guia-etapas          → escreve cada bloco (contexto→conceito→código→validação→critério de aceite) → 03-etapas/*.md
5. guia-publish         → gera o HTML final (delega à skill visual-explainer) → 04-publicacao.md
```

Requisitos mudaram no meio do caminho? Diga **"guia-iterate"** em vez de recomeçar — ele atualiza
o artefato certo e propaga a cascata para os subsequentes.

---

## Ver guia ativo

```
cat .claude/guias/{slug}/STATUS.md
```

Ou liste todos os guias:

```bash
ls .claude/guias/
```

## Retomar um guia em andamento

| Fase | Próximo passo |
|---|---|
| 0 — Tema capturado | guia-escopo |
| 1 — Escopo definido | guia-roteiro |
| 2 — Roteiro desenhado | guia-etapas |
| 3 — Etapas escritas | guia-publish |
| 4 — Publicado | — |
