# .claude/guias/ — histórico de guias passo-a-passo

Cada subpasta aqui corresponde a um guia didático iniciado via `/novo-guia` (ou `guia-brainstorm`).
Um guia é um **tutorial hands-on de implementação** para qualquer assunto técnico — não um projeto
de código. A saída final é uma página HTML autocontida, no espírito de um guia de aula ao vivo:
conceito antes de código, resultado observável a cada etapa, critério de aceite explícito.

## Estrutura por guia

```
.claude/guias/
└── {slug-do-guia}/            ← criado pelo guia-brainstorm
    ├── STATUS.md               ← fase atual + checklist
    ├── 00-tema.md               ← assunto, público-alvo, material-fonte, tipo de guia
    ├── 01-escopo.md             ← objetivos de aprendizagem, pré-requisitos, glossário, jornada
    ├── 02-roteiro.md            ← quebra em blocos (contextualização/prep/implementação/validação/apêndices)
    ├── 03-etapas/
    │   ├── 01-{slug-etapa}.md   ← contexto → conceito → código → validação → critério de aceite
    │   └── ...
    └── 04-publicacao.md        ← aponta para o HTML final gerado + notas de retro
```

## Fluxo de fases

```
0. 00-tema.md        /novo-guia → guia-brainstorm
1. 01-escopo.md       guia-escopo
2. 02-roteiro.md      guia-roteiro (consulta KBs técnicos + .claude/kb/design-instrucional/)
3. 03-etapas/*.md     guia-etapas (1 arquivo por bloco do roteiro)
4. 04-publicacao.md   guia-publish (delega renderização HTML à skill visual-explainer)
```

## STATUS.md — o dashboard por guia

```bash
cat .claude/guias/{slug}/STATUS.md
```

Ou liste todos:

```bash
ls .claude/guias/
```

## Como iniciar um novo guia

```
/novo-guia
```

ou ative o agente diretamente:

```
guia-brainstorm
```

## Como retomar um guia em andamento

Leia o STATUS.md do guia e retome o passo correspondente:

| Fase | Próximo passo |
|---|---|
| 0 — Tema capturado | guia-escopo |
| 1 — Escopo definido | guia-roteiro |
| 2 — Roteiro desenhado | guia-etapas |
| 3 — Etapas escritas | guia-publish |
| 4 — Publicado | — |

Requisitos mudaram no meio do caminho (novo bloco, mudança de público-alvo)? Use `guia-iterate`
em vez de reescrever do zero.
