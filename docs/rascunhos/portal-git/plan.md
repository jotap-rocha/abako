# Plano — Fundamentos de Git e CI/CD nos gates do Harness

> **Repositório:** `agent-harness-canonico-v2` (framework canônico)
> **SCM / CI:** Azure DevOps (Azure Repos + Azure Pipelines)
> **Branch default:** `master`
> **Objetivo:** estabelecer um padrão de fluxo Git aplicável a repositórios de engenharia de dados e de software, propagável via `/install-harness`.

---

## 1. Contexto e restrições

### 1.1 Situação atual

Os gates do harness cobrem qualidade de código (`/validar`, `revisor-codigo`, DoD, sync-context), mas não cobrem higiene de controle de versão. Não há padrão para criação de branch, mensagem de commit, corpo de Pull Request ou estratégia de merge. Agentes e humanos podem trabalhar diretamente no tronco.

### 1.2 Restrições que definem o desenho

| Restrição | Consequência |
|---|---|
| Sem permissão `Edit policies` nem Project Administrator no Azure DevOps | Não é possível exigir PR, exigir build verde, limitar tipo de merge nem impedir push no tronco |
| Azure Repos não suporta hook Git server-side | Toda validação local é contornável (`--no-verify`, clone sem bootstrap) |
| Time com pouca experiência em CI/CD | Carga cognitiva é o principal risco de adoção, acima de qualquer questão técnica |
| **O time já utiliza Pull Request** | O trabalho não é criar o hábito, é padronizá-lo — o ponto de partida é melhor do que parece |

### 1.3 Declaração obrigatória

Esta declaração deve constar no material entregue ao time:

> Nesta etapa, **nenhum gate impede de fato** uma ação errada. Todos podem ser contornados.
> O objetivo não é trancar a porta — é tornar o caminho certo mais fácil que o errado e
> tornar o errado **visível**.

Omitir isso cria falsa sensação de segurança, que é pior do que não ter gate algum, porque desaparece do radar.

---

## 2. Objetivo e estratégia

O plano opera em três camadas, construídas nesta ordem:

```
CONVENÇÃO   →  o comando certo já faz a coisa certa
                (/nova-branch, template de PR, hooks locais)

DETECÇÃO    →  pipeline e relatório semanal tornam o desvio visível
                (funciona sem permissão nenhuma)

POLICY      →  quando a permissão for concedida, tranca o que já virou hábito
                (pedido protocolado desde o primeiro dia)
```

A sequência importa: a detecção produz os números que justificam o pedido de permissão, que habilita a prevenção. Sem evidência, o pedido não é priorizado pelo time de Azure DevOps.

---

## 3. Fase 0 — Medir antes de intervir

Prescrever gates sem saber quais práticas estão sendo violadas é palpite. A API REST do Azure DevOps é somente leitura neste levantamento e **não exige permissão especial**.

**Script:** `scripts/baseline_repo.py` — últimos 90 dias, por repositório.

| Métrica | Pergunta que responde |
|---|---|
| % de commits em `master` sem PR associado | Commit direto no tronco é problema real? |
| Distribuição de nomes de branch | Existe padrão emergente ou caos? |
| Tamanho médio de PR (arquivos / linhas) | O problema é branch ou lote grande? |
| Tempo de vida médio da branch | Há branch vivendo semanas? |
| Tempo entre abertura do PR e merge | Revisão é gargalo? |
| Tipo de merge efetivamente usado | Já é squash? |
| Número real de aprovações por PR | PR é revisão ou carimbo? |
| Varredura de segredos no histórico | Existe passivo a rotacionar? |

**Saída:** `docs/baseline/<repo>-<data>.md`.

Esse relatório tem dois usos: priorizar quais gates importam e **instruir o pedido de permissão** (§8). Um número concreto — "23% dos commits na master não passaram por PR" — prioriza um chamado; "queremos boas práticas" não.

---

## 4. Modelo de branching

### 4.1 Decisão

```
master (tronco único)
   ↑
   └── PR (squash merge) ── feat|fix|chore/<escopo-kebab>

tag prod-YYYYMMDD (ou vX.Y.Z) a cada entrega validada em produção
```

### 4.2 Última versão válida de produção: tag, não branch

O requisito de ter sempre identificada "a última versão válida da esteira de produção" pede um **ponteiro imutável**. Uma branch é a ferramenta errada para isso.

| | Duas branches vivas | Tag de produção |
|---|---|---|
| Disciplina contínua exigida | Merge-back a cada hotfix | Nenhuma |
| Modo de falha típico | Hotfix não retorna à branch de integração; o bug ressuscita semanas depois | Não existe |
| Clareza para quem está aprendendo | "Qual das duas era produção mesmo?" | `prod-2026-08-05` é autoexplicativo |
| Auditoria | Reconstruída a partir do histórico | Imediata |
| Custo de implantação | Alto (processo + treinamento) | `git tag` no fechamento da entrega |

Com um time em formação, duas branches de longa duração é a decisão mais cara do plano e a que menos entrega. A tag resolve o requisito com custo próximo de zero.

Se no futuro houver cadência formal de release, a evolução natural é `master` + `release/*`. O par `main` + `master` deve ser evitado em qualquer cenário: os nomes não carregam semântica e ninguém memoriza qual é qual.

### 4.3 Rejeitado explicitamente

- Dois troncos vivos com papéis distintos.
- Trabalho direto no tronco.
- Force-push no tronco.
- Renomear `master` para `main` nesta etapa — a mudança de branch default exige a permissão `Edit policies`, que ainda não temos.

---

## 5. Contrato mínimo

Cabe em uma página. É o Anexo A.

### 5.1 Branch

```
{tipo}/{escopo-kebab}

tipos: feat | fix | chore
escopo: até 40 caracteres, kebab-case, sem acento

feat/gate-branch-isolada
fix/parser-data-nula
chore/atualiza-dependencias
```

Proibidos: `tmp`, `teste`, nome de pessoa, data solta, `nova-branch`.

**Três tipos, não oito.** Times em formação travam discutindo se algo é `refactor` ou `chore`. Tipos adicionais entram depois, sob demanda do próprio time — nunca antes.

### 5.2 Commit durante o desenvolvimento

Mensagem livre, com aviso não-bloqueante sugerindo o padrão. Esses commits desaparecem no squash e não vale gastar capital político neles. Commit pequeno continua sendo melhor que commit grande, por razões de revisão, não de formato.

### 5.3 Título do Pull Request — o ponto de controle real

```
{tipo}({escopo}): {resumo de até 72 caracteres}

feat(ingestao): adiciona particionamento por data de carga
fix(dev-loop): corrige drift de sincronização
```

Este é o texto que sobrevive na `master` após o squash. Concentrar a formalidade aqui traz três ganhos: uma única mensagem formal por entrega em vez de dez, revisão por um humano no momento do PR (que é onde o aprendizado acontece) e alinhamento com o commit que de fato fica no histórico.

> **Detalhe operacional a decidir e documentar:** ao completar o PR, o Azure DevOps prefixa `Merged PR NNN: ` na mensagem. Ou o prefixo é aceito — e os parsers de changelog usam regex tolerante, `^(?:Merged PR \d+: )?...` — ou a mensagem é editada em "Customize merge commit message". Deixar implícito quebra qualquer automação de versionamento mais adiante.

### 5.4 Corpo do Pull Request

Arquivo `.azuredevops/pull_request_template.md`. Por ser apenas um arquivo versionado no repositório, **funciona imediatamente, sem qualquer permissão**.

```markdown
## O que muda
<!-- 1 a 3 bullets -->

## Como testei
<!-- checklist -->

## Checklist
- [ ] Branch no padrão `tipo/escopo`
- [ ] Título deste PR no padrão `tipo(escopo): resumo`
- [ ] Nenhum segredo ou credencial no diff
- [ ] Gate de qualidade verde localmente
```

### 5.5 Merge

**Squash**, sempre — histórico linear, uma entrega igual a um commit. Enquanto não houver a policy "Limit merge types", é convenção reforçada pelo checklist do revisor.

### 5.6 Antes de criar branch

Verificar se a `master` local está atrás de `origin/master` e atualizar. Automatizado dentro do comando (§6.1) para que ninguém precise lembrar.

---

## 6. Camada 1 — Convenção

### 6.1 Comando `/nova-branch`

Consolida em um passo o que hoje são cinco decisões:

```
1. git fetch origin
2. HEAD está no tronco? Se não, avisa e confirma.
3. master local atrás de origin/master? Se sim, atualiza.
4. Solicita tipo (feat/fix/chore) e escopo; valida e normaliza para kebab-case.
5. git switch -c {tipo}/{escopo}
6. Imprime o título de PR sugerido, para uso na abertura do PR.
```

**Princípio de desenho:** para um time em formação, automatizar vale mais que ensinar. A pessoa roda um comando; o conceito entra pelo uso repetido, não pelo documento.

### 6.2 Hooks locais via `core.hooksPath`

A pasta `.git/hooks` não é versionada. Sem tratamento explícito, quem clonar o repositório não terá gate algum.

- Pasta versionada `.githooks/`
- `git config core.hooksPath .githooks` executado por script de bootstrap
- Bootstrap acionado pelo `/install-harness` e incluído no onboarding

| Hook | Verificação | Severidade inicial |
|---|---|---|
| `pre-commit` | Segredos no diff | **Bloqueante desde o primeiro dia** |
| `pre-push` | Push em `master` / `main` | Aviso → bloqueante após 4 semanas |
| `commit-msg` | Sugere Conventional Commits | Aviso permanente |

Segredo é o único caso que justifica bloqueio imediato: vazamento não se resolve com revert, se resolve com rotação de credencial. É o único gate cujo custo de falha é irreversível.

### 6.3 Mensagens de erro como material didático

Para este time, o hook é o principal canal de treinamento. Toda mensagem de erro traz o que fazer, com exemplo colável e a razão:

```
✗ Você está na branch 'master'.

  Crie uma branch de trabalho:
      /nova-branch
  ou manualmente:
      git switch -c feat/meu-escopo

  Por quê: alterações feitas direto no tronco não passam por revisão e não
  podem ser desfeitas sem afetar todo mundo.
```

### 6.4 Rollout gradual

Semanas 1 a 4 em **modo aviso**, com data de corte anunciada previamente. Bloqueio imediato em time inexperiente leva à desativação do gate — e gate desativado é pior que gate inexistente, porque some da medição.

---

## 7. Camada 2 — Detecção

### 7.1 Pipeline de guardrails

Um pipeline com CI trigger em push no tronco não depende de branch policy para existir. Ele não impede — denuncia.

```yaml
# azure-pipelines-guardrails.yml
trigger:
  branches:
    include: [ master ]
```

Verifica a cada push no tronco:

1. O commit chegou via Pull Request?
2. O título do PR segue o padrão?
3. O nome da branch de origem segue o padrão?
4. Há segredos no diff?
5. Registra o resultado em `metrics/git-hygiene.jsonl`

> **Observação técnica:** o trigger `pr:` em YAML **não funciona** no Azure Repos — ele é suportado apenas para GitHub e Bitbucket Cloud. A validação em Pull Request nasce exclusivamente da branch policy de Build Validation, e por isso pertence à Onda B (§8). Pull Requests em rascunho também não disparam validação.

### 7.2 Relatório semanal

Um markdown por repositório, publicado no canal do time. **Agregado por repositório, nunca por pessoa** — o objetivo é governança de aprendizado, não atribuição de culpa.

---

## 8. Camada 3 — Pedido de policies em três ondas

Protocolado na Fase 0, em paralelo com todo o resto. A fila de um time terceiro é item de *lead time*, não de maturidade interna: adiar o pedido soma a fila deles depois do nosso prazo, em vez de sobrepor.

**Pedir a permissão estreita:** `Edit policies` no nível de repositório, restrita aos repositórios do time. Não pedir Project Administrator — esse pedido trava em qualquer organização com governança. Vale registrar que, desde o sprint 224 do Azure DevOps, essa permissão não é mais concedida automaticamente a quem cria uma branch; precisa ser atribuída explicitamente.

### Onda A — solicitar imediatamente

Como o time já utiliza Pull Request, estas policies apenas formalizam um hábito existente. Custo de aprendizado próximo de zero.

| Policy | Efeito |
|---|---|
| Require a minimum number of reviewers = 1 | Formaliza o que já ocorre |
| Bloqueio de push direto (efeito automático de policy `Required`) | Fecha o gate de trabalho no tronco |
| Limit merge types = Squash only | Fecha o gate de padrão de merge |

Complemento indispensável: negar `Bypass policies when pushing` ao grupo Contributors. Sem isso, a policy é decorativa.

### Onda B — 4 a 8 semanas

| Policy | Pré-requisito |
|---|---|
| Build validation (`Required`) | Pipeline estável, sem vermelho intermitente |

Esta é a única onda que realmente depende de maturidade. Vermelho falso trava o time inteiro e queima a credibilidade da iniciativa. Só promover após duas semanas consecutivas de pipeline verde rodando em modo detecção.

### Onda C — maturidade

Work item obrigatório, resolução de comentários e revisores automáticos por caminho. O equivalente de CODEOWNERS no Azure Repos é a policy "Automatically included reviewers" — não existe arquivo de ownership versionado. Os filtros de caminho precisam começar com `/` ou wildcard e exigem ao menos um padrão de inclusão positivo; regra composta só de exclusões nunca dispara.

### Texto do pedido

Anexo B. Estrutura: número do baseline → risco concreto → policy específica → escopo mínimo de permissão → alternativa que dispensa a permissão.

---

## 9. Perfil de repositório

O gate `/validar` assume implicitamente uma aplicação Python. Essa premissa quebra no primeiro repositório de engenharia de dados. Introduzir no `CLAUDE.md` do projeto-filho:

```yaml
repo_profile: python-app | databricks-dab | dbt | sql-migrations | docs-only
```

| Perfil | Contrato de validação |
|---|---|
| `python-app` | ruff, mypy, pytest |
| `databricks-dab` | `databricks bundle validate`, ruff nos módulos, teste unitário do código extraído dos notebooks, CLI com versão fixada, controle de concorrência por target |
| `dbt` | `dbt parse`, `dbt build --select state:modified+` |
| `sql-migrations` | sqlfluff, idempotência de DDL, script de rollback obrigatório |
| `docs-only` | links quebrados, frontmatter, verificação de espelho `.claude` ↔ `.cursor` |

Comum a todos os perfis: varredura de segredos.

Dois pontos específicos de dados que o contrato precisa acomodar: notebooks produzem diff ruidoso e só têm cobertura real quando a lógica é extraída para módulos; e ambiente, em Databricks, significa workspace com service principal e separação dev/staging/prod, não deploy de aplicação.

> **Nomenclatura:** Databricks Asset Bundles passaram a se chamar Declarative Automation Bundles. Manter os dois termos na documentação durante a transição.

---

## 10. Integração no harness

### 10.1 Rule transversal, agnóstica de SCM

`.claude/rules/git-hygiene.md` e espelho `.cursor/rules/git-hygiene.mdc`, com `alwaysApply: true`.

A rule declara **invariantes**, não fornecedor:

- Trabalho acontece em branch isolada.
- Toda entrega no tronco passa por revisão.
- Toda entrega tem título convencional.
- Nunca há segredo no diff.

O fornecedor é resolvido por adapter (`scm: azure | github` no `CLAUDE.md` do projeto-filho), que decide entre `az` e `gh`. Cravar "SCM = Azure DevOps" dentro de uma rule com `alwaysApply` faria todo projeto-filho hospedado em GitHub carregar uma regra falsa.

### 10.2 Fonte única do contrato

`git-hygiene.yaml` na raiz do canônico, contendo as expressões regulares de branch e de título de PR. Consumido por: scripts locais, hooks, pipeline de detecção e gerador do texto de policy.

Sem essa centralização, a mesma regex passa a existir em cinco lugares — rule `.claude`, rule `.cursor`, script de branch, script de commit e YAML do pipeline — e diverge silenciosamente.

### 10.3 Wiring nos agentes

| Agente | Mudança |
|---|---|
| `prompt-crafter` | Seção `## Git` no PROMPT, com branch sugerida |
| `dev-loop-executor` | Step 0 `GIT_PREFLIGHT` (branch isolada + sincronia com o remoto); step final opcional de commit |
| `harness-brainstorm` | Oferece `/nova-branch` quando detecta HEAD no tronco |
| `harness-build` | Verifica branch isolada antes do primeiro passo |
| `harness-ship` | Gera o título de PR convencional, apresenta o checklist e cria a tag `prod-*` quando aplicável |
| `revisor-codigo` | Sinaliza, sem bloquear, diff produzido no tronco |

Todo artefato em `.claude/` espelhado em `.cursor/` na mesma sessão.

### 10.4 Teste do próprio gate

Fixtures com nomes de branch e títulos de PR válidos e inválidos. Sem isso, o componente responsável por validar tudo passa a ser o menos testado do sistema.

### 10.5 Template de pipeline

Os projetos-filho consomem um template central via `extends`, apontando para o repositório canônico — não recebem uma cópia do YAML. Cópia por repositório garante divergência e impede correção centralizada.

---

## 11. Mapa dos gates

| Gate | Mecanismo | Camada | Fase |
|---|---|---|---|
| Não desenvolver no tronco | `pre-push` + preflight do agente → policy Onda A | Convenção → Policy | 1 → 5 |
| Padrão de nome de branch | `/nova-branch` + detecção | Convenção | 1 |
| Padrão de mensagem | Aviso no `commit-msg` + título do PR validado | Convenção | 1 |
| Padrão de Pull Request | `.azuredevops/pull_request_template.md` | Efetivo desde já | 1 |
| Padrão de merge | Checklist do revisor → policy Onda A (squash only) | Convenção → Policy | 1 → 5 |
| Última versão válida de produção | Tag `prod-*` sobre tronco único | Efetivo desde já | 2 |
| Tronco sincronizado antes de branchar | Passo 3 do `/nova-branch` | Convenção | 1 |
| Segredo no diff | `pre-commit` bloqueante + pipeline de detecção | Convenção + Detecção | 1 |

---

## 12. Fases de entrega

### Fase 0 — Baseline e pedido (2–3 dias, paralelo a tudo)
- [ ] `baseline_repo.py` executado nos repositórios do time
- [ ] Relatório de baseline publicado
- [ ] Pedido de `Edit policies` (Onda A) protocolado junto ao time de Azure DevOps
- [ ] Decisões registradas em ADR: tronco único + tag, squash merge, três tipos

### Fase 1 — Caminho fácil (3–5 dias)
- [ ] Cheatsheet de uma página (Anexo A) — **entregar antes dos scripts**
- [ ] `.azuredevops/pull_request_template.md`
- [ ] Comando `/nova-branch`
- [ ] `.githooks/` + bootstrap de `core.hooksPath`
- [ ] `pre-commit` de segredos bloqueante; demais hooks em modo aviso
- [ ] `git-hygiene.yaml` como fonte única
- [ ] Rule `git-hygiene` + espelho `.cursor/`

### Fase 2 — Detecção (2–3 dias)
- [ ] `azure-pipelines-guardrails.yml` com CI trigger em `master`
- [ ] `metrics/git-hygiene.jsonl`
- [ ] Relatório semanal automatizado
- [ ] Tag `prod-*` no `harness-ship`

### Fase 3 — Habilitação do time (contínuo, 4 semanas)
- [ ] Sessão de 45 minutos: por que branch, por que PR, por que squash
- [ ] Rodada de PRs acompanhados em pareamento
- [ ] Data de corte anunciada para os hooks bloqueantes
- [ ] Retrospectiva na semana 4: o que atrapalhou na prática?

Esta é a única fase sem entregável técnico e é justamente a que determina se as demais pegam.

### Fase 4 — Perfis de repositório (3–5 dias)
- [ ] `repo_profile` no `CLAUDE.md` dos projetos-filho
- [ ] Contrato de validação por perfil
- [ ] Template central de pipeline consumido via `extends`

### Fase 5 — Policies (quando a permissão for concedida)
- [ ] Onda A aplicada e verificada
- [ ] Baseline remedido: comparação antes/depois
- [ ] Onda B após duas semanas de pipeline verde
- [ ] Break-glass documentado: quem pode contornar, em que situação, com que registro

---

## 13. Métricas de adoção

Medidas mensalmente contra o baseline da Fase 0, sempre por repositório.

| Métrica | Meta em 90 dias |
|---|---|
| Commits em `master` originados de PR | > 95% |
| Branches dentro do padrão | > 90% |
| Títulos de PR dentro do padrão | > 80% |
| Segredos detectados em PR | 0 |
| Tempo de vida médio de branch | < 3 dias |
| Tempo entre abertura do PR e merge | < 1 dia útil |

---

## 14. Critérios de aceite

1. Existe baseline publicado com números, anterior à introdução de qualquer gate.
2. `/nova-branch` cria branch no padrão e recusa criar a partir de tronco desatualizado.
3. O template de PR aparece automaticamente ao abrir Pull Request no Azure Repos.
4. Clone limpo seguido de bootstrap ativa os hooks — `core.hooksPath` verificável.
5. Tentativa de commit contendo segredo é bloqueada.
6. O pipeline de detecção registra commit direto no tronco em `metrics/git-hygiene.jsonl`.
7. Existe tag `prod-*` apontando para a última entrega validada em produção.
8. O pedido de `Edit policies` está protocolado, com número de chamado rastreável.
9. Artefatos espelhados entre `.claude` e `.cursor`.
10. O cheatsheet de uma página existe e o time confirmou leitura.

Nenhum critério afirma que um gate bloqueia. Sem a permissão, não bloqueia — e prometer o contrário seria inserir uma mentira no critério de aceite.

---

## 15. Riscos e mitigações

| Risco | Mitigação |
|---|---|
| Time desativa os hooks | Modo aviso primeiro, mensagens didáticas, relatório não-punitivo |
| Pedido de permissão trava na fila | Protocolado na Fase 0 com evidência numérica; as Fases 1 a 4 não dependem dele |
| Falsa sensação de segurança | Declaração explícita do §1.3, repetida no cheatsheet |
| Vermelho falso na Onda B queima a iniciativa | Build validation só após duas semanas de verde consistente |
| Sobrecarga conceitual | Três tipos, um comando, uma página; ampliar apenas sob demanda do time |
| Prefixo `Merged PR NNN:` quebra changelog | Decisão documentada no §5.3 antes de automatizar versionamento |
| Divergência `.claude` ↔ `.cursor` | Verificação no pipeline de detecção |
| Hooks ausentes em clone novo | Bootstrap no `/install-harness` + verificação no pipeline de detecção |
| Repositório-filho hospedado em GitHub | Rule agnóstica + adapter `scm` (§10.1) |

---

## 16. Fora de escopo nesta etapa

- Renomear `master` para `main` (depende de `Edit policies`).
- Duas branches de longa duração.
- Deploy automático em produção.
- Ambientes com aprovação manual (depende da Onda B consolidada).
- Work item obrigatório e revisores automáticos (Onda C).
- Migração do remote para GitHub.

---

## Anexo A — Cheatsheet do time

```
COMEÇAR UMA TAREFA
  /nova-branch          → atualiza a master e cria a branch no padrão

NOMES DE BRANCH
  feat/    nova funcionalidade
  fix/     correção
  chore/   manutenção, dependências, configuração
  exemplo: feat/ingestao-particionada

DURANTE O TRABALHO
  Commits com mensagem livre. Commit pequeno é melhor que commit grande.
  Nunca commite senha, token ou string de conexão.

ABRIR O PULL REQUEST
  Título:   tipo(escopo): resumo curto
  exemplo:  feat(ingestao): adiciona particionamento por data
  Preencha o template. Este título fica no histórico para sempre.

FECHAR O PULL REQUEST
  Squash merge. Sempre.

REGRA DE OURO
  Nunca trabalhe direto na master.
  Se estiver na master, pare e rode /nova-branch.
```

---

## Anexo B — Estrutura do pedido ao time de Azure DevOps

**Assunto:** Solicitação de permissão `Edit policies` — repositórios `<lista>`

1. **Contexto (duas linhas).** Padronização do fluxo Git; o time já utiliza Pull Request.
2. **Evidência.** Números do baseline: `X%` dos commits em `master` nos últimos 90 dias não passaram por Pull Request; `Y` PRs concluídos sem revisão efetiva; `Z` branches fora de qualquer padrão.
3. **Risco concreto.** Alteração chegando a produção sem revisão nem rastreabilidade, sem nenhum controle preventivo disponível hoje.
4. **O que pedimos.** Permissão `Edit policies` **no nível de repositório**, restrita à lista acima. Não solicitamos Project Administrator.
5. **O que ativaremos (Onda A).** Mínimo de um revisor e limitação de tipo de merge a squash. Consequência direta: push no tronco passa a ser bloqueado.
6. **O que não ativaremos agora.** Build validation, que aguarda pipeline estável e será solicitado separadamente.
7. **Alternativa caso a permissão não seja concedida.** Que o próprio time de Azure DevOps aplique as policies da Onda A nos repositórios listados. Nosso objetivo é a policy, não a permissão.

O item 7 é o mais importante do documento: ele remove o único motivo legítimo de recusa.

---

## 17. Próximos passos

1. Executar `baseline_repo.py` e publicar os números.
2. Protocolar o pedido do Anexo B com os números em mãos.
3. Escrever o Anexo A e apresentá-lo ao time em 20 minutos.
4. Rodar `/to-tasks` sobre a Fase 1, com critérios de aceite testáveis por exit code.
