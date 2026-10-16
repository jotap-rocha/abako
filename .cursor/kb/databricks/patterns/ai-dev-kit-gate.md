# AI-DEV-KIT Databricks — gate de pré-requisito SDD

## Âncora normativa

- **Escopo:** processo SDD (`harness-brainstorm` passo **4a-bis**, `harness-define` passo **2a**).
- **Não substitui** checks mecânicos DE (`data-engineering.yaml`) — é gate **humano** de pré-requisito.
- **Ortografia:** **AI-DEV-KIT** (hífen, maiúsculas) — mesmo nome usado pelo administrador da organização.

## O que é

O **AI-DEV-KIT Databricks** é o pacote organizacional instalado **no repositório alvo** antes de
iniciar SDD ou Dev Loop em projetos Databricks. Ele traz:

- Vocabulário e convenções modernas (SDP, DABs, Unity Catalog, system tables).
- Agents/skills/commands alinhados ao workspace Databricks da organização.
- Templates e wiring que o Agent Harness **não** substitui — complementa o `/install-harness`.

Fonte de modernização no canônico: pesquisa `ai-dev-kit-main-databricks` (ver
`docs/rascunhos/data-engineering/pesquisa-4-repos-pipelines-boas-praticas.md`).

## Quando acionar

| Condição | Gate |
|---|---|
| Runtime **Databricks** declarado no brainstorm (passo 4a) | **4a-bis** obrigatório |
| Runtime Spark local | N/A — pule 4a-bis |

## Pergunta ao usuário (hard-stop)

```
O AI-DEV-KIT Databricks está instalado neste repositório?
  a) Sim — instalado e verificado pelo time
  b) Não — ainda não foi instalado
  c) Não sei do que se trata
```

## Regras de decisão

| Resposta | Ação do agente |
|---|---|
| **a) Sim** | Continue o SDD (Medallion 4b, slug, artefatos). Registre confirmação humana no `00-ideia.md`. |
| **b) Não** | **Encerre o brainstorm.** Não crie `00-ideia.md` nem artefatos SDD. Instrua instalar o kit e retomar `/novo-projeto`. |
| **c) Não sei** | **Encerre o brainstorm imediatamente.** Oriente contato com o **administrador** do harness/Databricks. **Não** invente o que é o kit. **Não** prossiga. |

## Mensagem padrão ao encerrar (b ou c)

```text
Brainstorm encerrado: projetos Databricks exigem AI-DEV-KIT instalado no repositório
e confirmação humana de que o time conhece o kit. Entre em contato com o administrador
para instalação ou esclarecimento. Retome /novo-projeto quando o kit estiver instalado
e você puder responder "Sim" à pergunta de instalação.
```

## Honestidade (§1.3)

- O gate **não** verifica mecanicamente a instalação — depende de **resposta humana explícita**.
- Sinais no filesystem (ex.: artefatos do kit, `databricks.yml` + SDP) podem ser **dica** ao agente
  para **perguntar** se há divergência com a resposta humana — **nunca** substituem a confirmação.
- Resposta **Sim** falsa é risco organizacional — administrador define processo de auditoria fora
  deste gate.

## Registro no 00-ideia.md

```markdown
## Runtime Pipeline (gate 4a)

Runtime: {spark-local|databricks}
Declaração: humana ({data})
Notas: {inconsistência tipo passo 4, se houver}

## AI-DEV-KIT (gate 4a-bis — só Databricks)

Instalado: {sim|não|não-sei}
Declaração: humana ({data})
Status gate: {aprovado|encerrado — motivo}
```

## Agents

- `harness-brainstorm` — pergunta e hard-stop
- `harness-define` — valida que 4a/4a-bis constam no `00-ideia.md` antes de fechar grill
