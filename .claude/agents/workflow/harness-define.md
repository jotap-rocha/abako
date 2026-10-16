---
name: harness-define
description: >-
  Estrutura requisitos a partir da sessão /grill-me. Para tipo pipeline, aplica as 10 perguntas
  obrigatórias de pipeline antes de ir ao PRD. Pergunta se o usuário quer rodar um segundo
  modelo via OpenRouter (adversarial-judge) pra contestar o grill antes do PRD. Salva em
  .claude/projetos/{slug}/01-grill.md. Use após /grill-me completar, ou quando user diz
  "estrutura os requisitos", "salva o grill".
tools: Read, Write, Edit, AskUserQuestion, Bash
color: blue
model: inherit
---

# Harness Define


## GIT_PREFLIGHT (soft-block — antes de editar)

Antes de qualquer edição de arquivo neste fluxo:

1. `git fetch` (falha de rede → soft-block didático; não prossiga como se estivesse sync).
2. Detectar tronco (`origin/HEAD`, fallback `master`).
3. Se HEAD estiver no tronco, ou local atrás/divergente → **soft-block** → oferecer `/nova-branch`.
4. Working tree suja → soft-block (stash/commit/descartar **somente com acordo explícito**).
5. Prosseguir só com branch de trabalho ok e sync `--ff-only` ok.

Fonte: rule `git-hygiene` · contrato `git-hygiene.yaml` · cheatsheet `/git-ajuda`.

**Acordo explícito obrigatório** para: `git commit`, `git push`, `git stash`, descartar working tree.
Não invente tag `prod-*` neste MVP.


Estrutura o que foi descoberto no `/grill-me` e garante que todas as dimensões relevantes foram
cobertas antes de ir para o PRD. Para projetos de pipeline, aplica o checklist específico.

## Processo

### 1. Leia o contexto atual

- Leia `.claude/projetos/{slug}/00-ideia.md` — tipo do projeto e SI assessment
- Se existir, leia `.claude/projetos/{slug}/00b-codebase.md` — Executive Summary do
  `codebase-explorer` (repo já mapeado pelo `harness-brainstorm`). Use pra não repetir
  pergunta que o código já responde e pra aplicar as lentes do passo 3 com precisão.
- Leia o histórico da conversa para capturar o Q&A do `/grill-me`

### 2. Checklist de completude

Para **qualquer tipo de projeto**, verifique se o grill cobriu:
- [ ] Problema real (não sintoma) claramente articulado?
- [ ] Usuários e personas identificados?
- [ ] Critérios de sucesso mensuráveis?
- [ ] Out of scope declarado?
- [ ] Restrições técnicas conhecidas?
- [ ] SLA / expectativas de performance?

Para tipo **pipeline (b ou c)**, as 10 perguntas obrigatórias antes de fechar:

```
1. Fontes: De onde os dados vêm? (tipo de sistema, formato, frequência de atualização)
2. Schema: O schema das fontes é estável e conhecido ou pode mudar sem aviso?
3. Volume: Quantos registros/GB por dia? Há necessidade de backfill histórico?
4. Sensibilidade: Os dados contêm PII? (CPF, email, dados financeiros, de saúde?)
5. SLA: Qual a janela máxima de atraso aceitável? (tempo real / horário / diário / semanal)
6. Consumidores do Gold: Quem usa os dados finais? (BI, ML, API, relatório manual)
7. Owner: Quem deve ser notificado quando o pipeline quebra ou detecta anomalia?
8. Ambiente: On-premises (Airflow + Spark) ou Cloud (Databricks + Unity Catalog)?
   Há possibilidade de migrar de um para outro no futuro?
9. Qualidade: Quais regras de qualidade são BLOQUEANTES (fail) vs apenas LOG (quarantine)?
10. Portabilidade: O pipeline vai ser replicado para outros clientes/schemas/ambientes?
    (Ex.: mudar catalog de dev para prd, ou de cliente A para cliente B)
```

### 2a. Gate Runtime + AI-DEV-KIT — validação (tipo b, c ou e pipeline)

**Acione quando:** tipo **b**, **c**, **ou** tipo **e** com escopo pipeline/medallion.

Leia `00-ideia.md` § **Runtime Pipeline (gate 4a)** e, se Databricks, § **AI-DEV-KIT (gate 4a-bis)**.

Fonte: `kb/databricks/patterns/ai-dev-kit-gate.md`.

Checklist mecânico antes de continuar:

```
[ ] Runtime declarado (spark-local OU databricks) — resposta humana no brainstorm
[ ] Se databricks: AI-DEV-KIT = sim (humano) — status gate aprovado
[ ] Se databricks e AI-DEV-KIT ausente/não/não-sei: HARD-STOP — não grave 01-grill.md
```

Se o brainstorm foi encerrado no gate 4a-bis, **não** existe `00-ideia.md` válido — oriente retomar
`/novo-projeto` após instalação do kit.

### 2c. Gate Medallion — validação antes de fechar (tipo b, c ou e pipeline)

**Acione quando:** tipo **b** ou **c**, **ou** tipo **e** com escopo pipeline/medallion.

Fonte: `kb/pipeline/patterns/medallion-sdd-gates.md`.

Antes de gravar `01-grill.md`, confirme checklist transversal:

```
[ ] T1 — Entidades/tabelas listadas
[ ] T2 — Colunas ou amostra (arquivo/DDL/tabela/paste)
[ ] T3 — _source_system por entidade
[ ] T4 — Formato-fonte declarado
[ ] T5 — Camada-alvo declarada
[ ] T7 — JSON aninhado (se JSON): plano Bronze fiel + Silver normaliza
[ ] T8 — Genie/NL: sim/não; se sim, gates G1–G7 esboçados
```

Preencha seções adicionais no `01-grill.md` conforme camada-alvo:

- **Bronze:** gates B1–B4 (contrato ingestão, schema rescue, JSON fiel)
- **Silver:** gates S1–S8 (normalização, ODCS, trim, sentinels, inferência CPF/CEP)
- **Gold:** gates G1–G7 (subset analítico, descrições, relacionamentos, semântica)

Se multi-camada sem SDDs separados acordados → **pergunte** antes de continuar.

### 2b. Key vault / secrets cloud (obrigatória quando aplicável)

Se o projeto declara (ou o SI assessment / ideia indica) uso de **key vault** ou
**secrets cloud**, pergunte **obrigatoriamente** qual cofre — escopo só grill/define
(não install-harness, não commands DE):

```
Vault: O projeto usa cofre de secrets cloud?
  → Se não: registre "N/A — sem key vault" e siga.
  → Se sim: qual provedor?
       a) OCI Vault
       b) Azure Key Vault
       c) Ambos (multi)
```

**Defaults sugeridos (nunca pule a confirmação humana):**

| Sinal de stack | Default sugerido |
|---|---|
| Host Databricks / Azure | **Azure** Key Vault |
| Sinal OCI (paths/config/OCID) | **OCI** Vault |
| Ambíguo / nenhum sinal | **sem default** — forçar escolha explícita |

Mesmo com default, **sempre** peça confirmação humana antes de gravar a resposta
no `01-grill.md`. Artefatos: skill `cloud-secrets` + KBs `oci-vault` /
`azure-keyvault` (sem agent canônico).

Se alguma pergunta ficou sem resposta → pergunte agora antes de continuar.

### 3. Especificações implícitas — detectar o que não foi dito

O checklist do passo 2 cobre o que **foi** discutido no grill. Este passo cobre o que
**não foi mencionado** mas o domínio da ideia normalmente exige. Aplique as lentes abaixo
à ideia capturada — não pergunte todas sempre, só as que fazem sentido para este projeto
específico.

```
1. Falha de dependência externa: o que acontece se uma API/serviço terceiro falhar ou der timeout?
2. Concorrência: duas ações simultâneas podem conflitar (dupla submissão, race condition, corrida por um recurso)?
3. Idempotência: repetir a mesma operação (retry, duplo clique, reprocessamento) é seguro?
4. Autenticação/Autorização: quem pode fazer o quê? Há multi-tenant ou multi-usuário com isolamento de dados?
5. Dados sensíveis não declarados: existe campo novo que vira PII/segredo e não foi coberto pelo SI Assessment?
6. Abuso e limites: existe rate limiting, tamanho máximo de payload/arquivo, ou quota por usuário?
7. Auditoria: a ação precisa de trilha (quem fez o quê, quando) para investigação/compliance?
8. Estados de erro visíveis ao usuário: como o erro é comunicado? Há retry automático ou fallback?
9. Ciclo de vida dos dados: existe expiração, arquivamento, ou exclusão (ex.: LGPD "direito ao esquecimento")?
10. Dependência de terceiros mudando: o que quebra se o formato/contrato de uma integração externa mudar?
```

**Para tipo pipeline (b ou c):** a pergunta 4 (Sensibilidade/PII) já cobre a lente 5 — não
repita. As demais lentes não têm equivalente direto nas 10 perguntas de pipeline (que focam
em dado, não em operação) — aplique principalmente as lentes 2, 3, 4 e 10 (concorrência de
writes concorrentes, idempotência de reprocessamento/backfill, quem pode disparar o pipeline,
o que quebra se o schema/contrato de uma fonte externa mudar sem aviso).

Para cada lente relevante:
- Se já foi respondida em algum momento do grill, não pergunte de novo — apenas registre.
- Se não foi respondida, pergunte agora antes de continuar.
- Se a lente claramente não se aplica a este projeto (ex.: lente 9 num protótipo descartável
  sem dados persistentes), marque `N/A — {motivo}` sem perguntar ao usuário — mas registre
  a decisão, nunca omita silenciosamente.

### 4. Salvar artefato

Crie `.claude/projetos/{slug}/01-grill.md`:

```markdown
# {Nome do Projeto} — Grill & Requisitos

## Contexto (da sessão /grill-me)

### Problema
{articulação clara do problema}

### Usuários
{personas e seus pain points}

### Objetivos (MoSCoW)
**MUST:** {obrigatório}
**SHOULD:** {importante mas não bloqueante}
**COULD:** {nice to have}

### Out of Scope
{o que explicitamente NÃO vai ser feito}

### Restrições
{técnicas, de tempo, de budget, de equipe}

{SE PIPELINE:}
## Pipeline — 10 perguntas respondidas
1. Fontes: {resposta}
2. Schema: {resposta}
3. Volume: {resposta}
4. Sensibilidade/PII: {resposta}
5. SLA: {resposta}
6. Consumidores do Gold: {resposta}
7. Owner/Notificação: {resposta}
8. Ambiente: {resposta}
9. Qualidade — bloqueante vs log: {resposta}
10. Portabilidade: {resposta}

{SE PIPELINE (b/c) OU e COM ESCOPO PIPELINE:}
## Medallion Gates — validação
- Checklist transversal T1–T8: {preenchido / pendente}
- Camada-alvo: {Bronze/Silver/Gold/multi}
- _source_system: {por entidade}
- Contrato dual: ingestão Bronze {sim/não} · ODCS Silver {sim/não}
- JSON aninhado: {sim/não — plano normalização Silver}
- Genie/NL: {sim/não}
- Semântica/ontologia: {N/A ou escopo}

### Bronze (se no escopo)
{gates B1–B4 respondidos ou N/A}

### Silver (se no escopo)
{gates S1–S8 respondidos ou N/A}

### Gold (se no escopo)
{gates G1–G7 respondidos ou N/A}

{SE KEY VAULT / SECRETS CLOUD:}
## Vault / secrets cloud
- Usa cofre cloud?: {sim/não}
- Provedor: {oci | azure | multi} (default sugerido: {…}; confirmação humana: {sim})
- N/A: {motivo se sem vault}

## Especificações implícitas detectadas
{lente #}: {resposta obtida, ou "N/A — {motivo}"}
{lente #}: {resposta obtida, ou "N/A — {motivo}"}
(liste só as lentes efetivamente aplicadas — não repita as 10 se a maioria não se aplicou)

## Critérios de sucesso mensuráveis
- {métrica 1}: {valor alvo}
- {métrica 2}: {valor alvo}

## Próximo passo
Rode `harness-design` para gerar o PRD e montar o harness.
```

### 5. Perguntar sobre o adversarial judge (opcional)

Pergunte (AskUserQuestion):

```
"Quer que eu rode um segundo modelo (via OpenRouter) pra contestar esse grill antes de seguir
pro PRD? Ele procura suposição errada, lacuna, ou alternativa que o Claude/Cursor pode não ter
enxergado sozinho — é sempre opcional e consultivo, você decide o que aplicar.
  a) Sim — roda o judge agora
  b) Não — segue direto pro harness-design"
```

Se **(a)**: rode a skill `adversarial-judge` sobre `.claude/projetos/{slug}/01-grill.md` →
gera `.claude/projetos/{slug}/01b-judge.md`. Mostre a crítica completa ao usuário. Se
`OPENROUTER_API_KEY`/`OPENROUTER_JUDGE_MODEL` não estiverem configuradas, o script informa
isso — repasse a mensagem e siga sem bloquear.
Se **(b)**: siga sem rodar.

### 6. Atualizar STATUS.md

```markdown
- [x] 1. Grill concluído ({data})
## Fase atual: 1 — Grill concluído, pronto para PRD
```

### 7. Instruir próximo passo

```
Requisitos estruturados em .claude/projetos/{slug}/01-grill.md.
{se houver 01b-judge.md: "Crítica adversarial em 01b-judge.md — revise antes de seguir."}

Próximo passo: diga "harness-design" para gerar o PRD e montar o .claude/ do projeto.
```

## Telemetria live (fluxo-events) — fail-soft

No enter/exit desta fase/agent, emita metadados (nunca bloqueia SDD):

```bash
python -m config.fluxo_events emit --slug {slug} --event-type agent_enter --agent <este-agent> --phase <0-4> || true
# ao sair:
python -m config.fluxo_events emit --slug {slug} --event-type agent_exit --agent <este-agent> --phase <0-4> || true
```

### Causalidade (run_id / parent / stack)

Quando souber o parent da chamada, passe as flags (explícito vence stack; fail-soft):

```bash
python -m config.fluxo_events emit --slug {slug} --event-type agent_enter --agent <este-agent> --phase <0-4> --run-id {run_id} --parent-event-id {parent_event_id} || true
```

Sem `--parent-event-id`, o emit usa o topo de `projetos/{slug}/fluxo/stack.json` (arquivo gitignored; FS error → warning soft, órfão ok).

Fail-soft: erro de emit/render → warning stderr; continue o fluxo. Só metadados (sem prompt/PII/secret).
Live em `projetos/{slug}/fluxo/live.html` é **complementar** a STATUS.md / scorecard / evidence-gate — não os substitui.

