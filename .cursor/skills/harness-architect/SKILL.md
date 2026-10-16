---
name: harness-architect
description: >-
  Skill de entrevista que transforma o PRD (ou spec/documento de arquitetura) de um projeto
  num setup concreto de agent harness no diretório .claude/. Use SEMPRE que o usuário quiser
  planejar ou estruturar o harness de um projeto de código, montar ou andaimar o .claude/
  (CLAUDE.md, rules, skills, subagents, commands, hooks, settings, MCP), entender qual harness
  um projeto precisa, ou pedir para ser entrevistado/questionado sobre o projeto antes de gerar
  os arquivos de harness. Dispare mesmo com frases soltas — "me ajuda a pensar o harness desse
  projeto", "o que eu preciso no .claude pra isso", "prepara o repo pra um agente construir",
  "lê meu PRD e me pergunta o que falta pra montar o harness". A skill lê o PRD primeiro e só
  pergunta o que não consegue inferir.
---

# Harness Architect

Transforma um PRD num agent harness concreto no `.claude/`. O harness é o sistema ao redor do
modelo — **estado, ferramentas, execução e validação** — que faz um modelo virar um agente que
entrega. Esta skill conduz a fase que vem *antes* da primeira linha de código: projetar o
ambiente onde o agente vai trabalhar.

A skill não despeja perguntas genéricas nem gera arquivos no escuro. Ela segue a ordem certa:
**alinhar antes de gerar**. Lê o que já existe, infere o máximo, confirma, pergunta só o que
falta, e só então andaima o `.claude/`.

## Princípios que guiam a condução

Estes princípios não são decoração — eles determinam *o que* perguntar e *o que* gerar:

- **Alinhar antes de gerar.** A maior falha não é o código, é o desalinhamento. Leia o PRD e
  infira antes de perguntar. Nunca pergunte o que já está escrito no PRD.
- **Os quatro pilares são a lente.** Toda decisão de harness serve a um de: estado/memória,
  ferramentas, execução, validação. Se uma pergunta não mapeia num pilar, ela não pertence aqui.
- **Quem lê o quê.** Cada peça do `.claude/` responde uma pergunta diferente. Ao andaimar,
  declare para cada arquivo qual pergunta ele responde e quem o consome.
- **A janela é transitória; os arquivos lembram.** O que sobrevive a um reset de contexto é o
  que foi escrito no repositório (CLAUDE.md, ADRs, handoff, MEMORY.md). Memória é
  responsabilidade central do harness, não um plugin.
- **Todo erro vira um sinal permanente.** Pergunte como falhas devem virar regra, hook, teste ou
  skill — não um "run ruim" para repetir.
- **Comece mínimo (Ralph).** Não complique cedo demais. Recomende o menor harness que cobre os
  riscos reais do PRD; subagentes e orquestração só quando a tarefa pede.
- **Baseline da empresa, simples por padrão.** O time simula boas práticas reais — ADRs para os
  porquês, EDD como gate de aceite, rules curtas por área, gate hard no hook. Gere esse baseline,
  mas **sem inflar**: o mínimo que cobre os riscos do PRD, nunca um harness "enterprise" por reflexo.
- **O harness se move, não encolhe.** Não dimensione o harness ao modelo atual; dimensione aos
  riscos do projeto.

## Entradas

Antes de qualquer pergunta, localize e leia o material de origem:

1. **Ache o PRD canônico.** Prefira `PRD.md` (consolidado). Se houver vários docs tipo-PRD (ex.:
   `ideia.md` rascunho + `PRD.md` consolidado), trate o consolidado como verdade, os demais como
   histórico, e confirme com o usuário qual é o canônico. Sem nenhum PRD, peça onde está ou um
   resumo curto antes de prosseguir.
2. **Leia o `.claude/` já existente** — a skill quase sempre *complementa* um harness, não cria do
   zero.
3. **Detecte deriva antes de gerar.** Compare o que o PRD/CLAUDE.md dizem do harness com o que está
   no disco (rules, commands, agents, hooks). Liste divergências — arquivo que o doc cita mas sumiu,
   hook apontando pra script inexistente — e **sinalize ao usuário**; não scaffold por cima de um
   conflito.

## Workflow

### 0. CONTEXT_REBIND (obrigatório no 1º round — soft-block)

Antes de ler o PRD / andaimar, confirme que `CLAUDE.md`, `AGENTS.md`, `CONTEXT.md` e
`README.md` descrevem o **projeto-filho**, não o Agent Harness Canônico.

Soft-block se:
- título ou assinatura canônica (`Agent Harness Canônico — guia do agente`, texto de
  “framework do Agent Harness Method”);
- conteúdo ainda é stub/placeholder do install (`(preencher)`, sem domínio do filho).

Ação: pare e ofereça `/grill-with-docs`, `/grill-me` ou reescrita via esta skill; só
prossiga quando o contexto for do filho. Espelhe artefatos `.claude` ↔ `.cursor` quando
editar agents/skills/rules. Helpers: `looks_like_canonical_context` /
`needs_context_rebind` em `install_harness.py`.

### 1. Leia e infira (alinhar antes de gerar)

Leia o PRD por inteiro. Para cada um dos sete clusters de entrevista
(ver `references/interview-bank.md`), escreva o que você **já consegue inferir** do documento.
Exemplos do que costuma estar no PRD: a stack, os comandos, invariantes ("SQL somente leitura"),
a separação de fases, os KPIs/critérios de sucesso, a estratégia de avaliação.

**Leia também por camada da stack.** Identifique quais camadas o PRD prevê — backend, frontend,
db, IA/agente, ingestão, evals — e, para cada camada *presente*, derive as `rules/` e os `agents/`
que ela costuma exigir. O mapa camada → artefato está em `references/stack-layer-map.md` (leia antes
de planejar). Só gere artefato para camada que o PRD realmente tem — camada ausente não vira arquivo.

### 2. Apresente as inferências e pergunte só as lacunas

Mostre ao usuário, de forma compacta, o que você inferiu ("Pelo PRD, entendi X, Y, Z — confirma?")
e faça perguntas **apenas sobre o que o PRD não respondeu**. Pergunte em lotes pequenos, um
cluster por vez, nunca um questionário de 30 itens. Se a ferramenta de perguntas interativas
estiver disponível, use-a; senão, agrupe 2–3 perguntas por mensagem. O banco completo de perguntas,
com o que inferir e o artefato que cada resposta alimenta, está em `references/interview-bank.md` —
leia esse arquivo antes de entrevistar.

### 3. Sintetize o Harness Plan

Antes de colocar um `agent` novo no plano: esta skill é o **segundo caminho** deste canônico
que gera arquivo de agente (o primeiro é o `agent-creator`, que entrevista). Como aqui não há
entrevista, aplique o mesmo gate de redundância na mão — leia o Mapa de escalação em
`.claude/agents/README.md` e confirme que nenhum agente já existente (no canônico, ou já
copiado pro projeto alvo pelo `install-harness`) cobre >60% da responsabilidade antes de
planejar um agente novo. Se cobrir, o plano referencia o agente existente — não gera arquivo.

Quando os clusters estiverem cobertos, escreva um **Harness Plan**: uma tabela que mapeia cada
decisão → ao artefato do `.claude/` que a materializa → ao pilar que ela serve. Use exatamente
esta estrutura:

```markdown
# Harness Plan — [nome do projeto]

## Invariantes (sempre valem)
- ...

## Mapa decisão → artefato → pilar
| Decisão | Artefato no .claude/ | Pilar | Quem lê |
|---|---|---|---|
| ... | ... | ... | ... |

## O que NÃO entra agora (e por quê)
- ...
```

A seção "o que não entra agora" é obrigatória — ela aplica o princípio de começar mínimo e deixa
explícito o que foi deliberadamente adiado.

### 4. Confirme antes de gerar

Apresente o Harness Plan e peça confirmação. Não gere arquivos até o usuário validar o plano.
Esse passo é o "alinhar antes de gerar" aplicado à própria skill.

### 5. Andaime o .claude/

Com o plano confirmado, gere os arquivos. Use os templates de `references/claude-dir-templates.md`
(leia esse arquivo antes de gerar). Gere apenas os artefatos que o plano pediu — não crie um
subagente ou um hook que o projeto não precisa. Cada arquivo gerado deve trazer, no topo ou em
comentário, qual pergunta ele responde.

Ver `references/target-structure.md` para a árvore-alvo completa (o que cada arquivo é, inclusive
`AGENTS.md` vs `CLAUDE.md` e o esqueleto de `CONTEXT.md`) — leia antes de gerar.

### 6. Feche explicando "quem lê o quê" e o ciclo do erro

Encerre dizendo, em uma linha por arquivo gerado, qual pergunta ele responde. E deixe registrado
como o usuário deve tratar falhas dali em diante: toda falha real vira regra, hook, teste ou skill
— o harness aperta um dente a cada erro.

## Lembretes ao conduzir

- Não pergunte o que está no PRD. Inferir e confirmar é mais respeitoso que interrogar.
- Prefira recomendar o mínimo. Um `.claude/` com CLAUDE.md + um rule + um hook de validação já é
  um harness real; subagentes e commands entram quando há repetição ou delegação que justifique.
- Hooks vivem no `settings.json`, não num arquivo solto. Skills são pastas, não um `.md` avulso.
- Distinga gate *hard* (determinístico: lint, types, testes, evals) de verificação *soft* (LLM
  revisando LLM). Validação séria é hard.

## Telemetria live (fluxo-events) — fail-soft

No enter/exit desta fase/agent, emita metadados (nunca bloqueia SDD):

```bash
python -m config.fluxo_events emit --slug {slug} --event-type agent_enter --agent <este-agent> --phase <0-4> || true
# ao sair:
python -m config.fluxo_events emit --slug {slug} --event-type agent_exit --agent <este-agent> --phase <0-4> || true
```

Fail-soft: erro de emit/render → warning stderr; continue o fluxo. Só metadados (sem prompt/PII/secret).
Live em `projetos/{slug}/fluxo/live.html` é **complementar** a STATUS.md / scorecard / evidence-gate — não os substitui.

