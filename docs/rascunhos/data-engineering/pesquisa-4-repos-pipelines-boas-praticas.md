# Sketch revisado — evolução do harness canônico de Engenharia de Dados

> **Status:** sketch estratégico e técnico — **não** é especificação final nem implementação.  
> **Data:** 2026-08-06  
> **Origem:** consolidação adversarial da pesquisa realizada sobre quatro repositórios de engenharia de dados.  
> **Destino futuro:** evolução governada de rules, commands, skills, KBs, agentes, validadores e scaffolds do harness canônico em `.claude/` e `.cursor/`.

---

## 1. Propósito deste documento

Este arquivo define **como transformar evidências observadas em repositórios reais em um plano de evolução executável para o harness canônico de Engenharia de Dados**.

O objetivo não é copiar um projeto existente, nem promover automaticamente toda prática encontrada a mandato corporativo.

O objetivo é construir um canônico que:

1. diferencie evidência, recomendação e obrigação;
2. suporte mais de um perfil arquitetural;
3. transforme mandatos em verificações executáveis;
4. permita exceções formais e rastreáveis;
5. funcione em projetos novos e existentes;
6. mantenha compatibilidade entre IDEs e agentes;
7. priorize segurança, integridade, observabilidade e operação;
8. evite que o harness se torne apenas um catálogo de documentos e prompts.

---

## 2. Como o próximo LLM deve usar este arquivo

O próximo LLM deve tratar este documento como **diretriz para desenho**, não como autorização para implementar tudo de uma vez.

Ao propor mudanças no canônico, o modelo deve:

1. preservar a separação entre:
   - evidência observada;
   - prática recomendada;
   - mandato bloqueante;
   - proposta nova;
2. não transformar uma prática específica de um projeto em regra universal sem justificar aplicabilidade;
3. declarar para quais plataformas, engines e tipos de pipeline cada regra se aplica;
4. priorizar controles verificáveis por código, CI ou inspeção determinística;
5. evitar duplicar manualmente conteúdos entre `.claude/` e `.cursor/`;
6. definir uma fonte normativa única;
7. criar primeiro o kernel de conformidade e somente depois os agentes especializados;
8. tratar projetos existentes com baseline e melhoria progressiva;
9. exigir política de exceção para regras bloqueantes;
10. marcar explicitamente toda informação não suportada pelos repositórios como **proposta nova**.

---

## 3. Veredito consolidado

A pesquisa original oferece uma boa base comparativa e identifica corretamente que o maior problema atual é o espaço entre:

```text
prática documentada
        ↓
implementação parcial
        ↓
sem enforcement automático
```

Entretanto, promover diretamente os achados para KBs, skills e agentes criaria um risco relevante:

> O harness poderia explicar boas práticas de Engenharia de Dados sem conseguir provar que os projetos realmente as seguem.

A evolução recomendada deve seguir esta ordem:

```text
pesquisa e evidências
        ↓
decisões arquiteturais
        ↓
modelo normativo
        ↓
validadores executáveis
        ↓
CI, baseline e exceções
        ↓
scaffolds de referência
        ↓
skills, commands e agentes
        ↓
piloto brownfield
        ↓
expansão controlada
```

---

## 4. Fontes analisadas e papel de cada uma

| Fonte | Papel principal | Como deve ser usada |
|---|---|---|
| `data-agentic-ai-for-pipelines` | Fonte normativa e de organização agentic | Extrair princípios, IDs de mandatos, workflows e padrões on-premises |
| `databricks-varonis-dataflow-prd` | Referência de implementação fim a fim | Usar como evidência prática e blueprint conceitual, não como template universal |
| `dtbks-auditoria` | Produto real com gaps entre documentação e código | Transformar gaps recorrentes em casos de teste e checks do canônico |
| `ai-dev-kit-main-databricks` | Atualização de vocabulário e APIs modernas Databricks | Atualizar exemplos para SDP, DABs, system tables, SQL Alert v2 e `CLUSTER BY` |

### 4.1 Regra de uso das fontes

Nenhuma fonte deve ser considerada completa isoladamente.

A consolidação deve seguir o modelo:

```text
norma              → agentic kit
implementação      → Varonis
casos reais de gap → Auditoria
modernização       → AI Dev Kit
```

---

## 5. Níveis de evidência

Toda prática candidata ao canônico deve receber um nível de evidência.

| Nível | Descrição |
|---|---|
| `E1` | Apenas documentada ou recomendada |
| `E2` | Implementada em laboratório ou exemplo |
| `E3` | Implementada em um produto |
| `E4` | Operada em produção com comportamento conhecido |
| `E5` | Validada em múltiplos produtos, equipes ou perfis de carga |

### 5.1 Regra de promoção

Uma prática não deve virar mandato bloqueante apenas porque aparece implementada em um repositório.

Para se tornar bloqueante, a prática deve possuir:

- justificativa de risco;
- condição de aplicabilidade;
- validação determinística ou evidência objetiva;
- tratamento de exceção;
- owner responsável;
- impacto esperado;
- política para projetos existentes.

---

## 6. Categorias de regra

O canônico deve trabalhar com quatro categorias.

### 6.1 Universal

Aplica-se a todos os projetos de dados.

Exemplos:

- secrets não podem ser versionados;
- operações destrutivas precisam de proteção;
- todo pipeline deve ter owner;
- toda execução deve possuir identificador rastreável;
- dados sensíveis não podem aparecer em logs sem masking.

### 6.2 Condicional

Aplica-se apenas quando determinadas condições forem verdadeiras.

Exemplos:

- `schema rescue` aplica-se a ingestões de arquivos ou fontes sujeitas a drift;
- checkpoint aplica-se a pipelines streaming;
- `CLUSTER BY` aplica-se a workloads Delta compatíveis;
- AUTO CDC aplica-se a fontes e engines compatíveis.

### 6.3 Recomendada

Representa uma preferência arquitetural, mas não deve bloquear automaticamente.

Exemplos:

- uso de materialized views em Gold;
- preferência por SDP em novos projetos Databricks;
- uso de módulos SOLID separados por responsabilidade.

### 6.4 Informativa

Serve como orientação, referência ou exemplo.

Exemplos:

- exemplos de naming;
- templates de runbook;
- exemplos de card para Teams;
- diagramas medalhão.

---

## 7. Perfis arquiteturais

O canônico não deve impor uma única árvore ou uma única implementação para todos os pipelines.

Cada projeto deve declarar um perfil.

### 7.1 Perfis iniciais

1. `databricks-sdp-medallion`
2. `databricks-dlt-legacy`
3. `spark-yarn-airflow`
4. `batch-relational-jdbc`
5. `cdc-relational`
6. `streaming-event-driven`
7. `dbt-analytics`

### 7.2 Exemplo de declaração

```yaml
project_profile:
  platform: databricks
  pipeline_engine: sdp
  orchestration: databricks_workflows
  storage: delta_unity_catalog
  ingestion_mode: streaming
  source_type: files
  data_classification: confidential
  environment: production
```

### 7.3 Aplicabilidade de uma regra

```yaml
rule_id: DQ-M03
category: conditional
severity: blocker

applies_when:
  pipeline_engine:
    - sdp
    - dlt
  layer:
    - bronze
    - silver
  ingestion_mode:
    - streaming
```

---

## 8. Fonte normativa única

Deve existir uma fonte única de definição das regras.

Estrutura sugerida:

```text
canonical-data-engineering/
├── governance/
│   ├── rule-schema.yaml
│   ├── architecture-profiles.yaml
│   ├── severity-policy.yaml
│   ├── waiver-policy.yaml
│   ├── brownfield-policy.yaml
│   └── technology-lifecycle.yaml
├── rules/
│   ├── security/
│   ├── contracts/
│   ├── data-quality/
│   ├── observability/
│   ├── orchestration/
│   ├── operations/
│   ├── performance/
│   └── governance/
├── checks/
├── scaffolds/
├── knowledge/
├── agents/
└── adapters/
```

### 8.1 Regra para `.claude/` e `.cursor/`

`.claude/` e `.cursor/` devem ser artefatos gerados, não duas fontes manuais.

```text
canonical source
      ↓
adapter generator
      ├── .claude/
      └── .cursor/
```

Exemplo:

```bash
python scripts/generate_adapters.py --target claude
python scripts/generate_adapters.py --target cursor
python scripts/check_adapter_drift.py
```

---

## 9. Schema mínimo de uma regra

```yaml
id: SEC-M01
name: Secrets não podem existir no código
category: universal
severity: blocker
status: active
owner: data-platform-security

evidence_level: E5

rationale:
  risk: credential_exposure
  description: Evitar credenciais, tokens e webhooks versionados.

applicability:
  profiles:
    - "*"

validation:
  type: static_analysis
  command: canonical-data-check secrets

required_evidence:
  - scan_result

waiver:
  allowed: false

references:
  - agentic-kit
  - auditoria-gap-secrets
```

---

## 10. Severidade e resultado

| Severidade | Efeito |
|---|---|
| `blocker` | impede merge ou promoção |
| `critical` | exige correção antes de produção |
| `major` | exige plano de adequação |
| `warning` | não bloqueia, mas precisa ser registrado |
| `info` | recomendação ou orientação |

Saída padrão:

```text
PASS    SEC-M01 Nenhum secret detectado
FAIL    DQ-M03 Pipeline Silver sem tratamento de inválidos
WARN    PERF-R04 Estratégia de clustering não declarada
WAIVED  OBS-M02 Freshness temporariamente dispensada
N/A     CDC-M05 Regra não aplicável a pipeline batch
```

---

## 11. Kernel executável de conformidade

A primeira implementação do canônico deve ser uma suíte de validação.

### 11.1 Interface sugerida

```bash
canonical-data-check validate .
canonical-data-check explain DQ-M03
canonical-data-check baseline .
canonical-data-check report --format json
canonical-data-check report --format markdown
canonical-data-check compare --baseline baseline.json
```

### 11.2 Tipos de validação

- análise estática;
- validação de estrutura;
- inspeção de configuração;
- testes de contrato;
- testes de schema;
- execução de unit tests;
- validação de DAB;
- validação de Airflow DAG;
- inspeção de operações destrutivas;
- scanner de secrets;
- inspeção de observabilidade;
- inspeção de políticas de DQ;
- validação de documentação obrigatória.

### 11.3 Princípio central

> O agente não decide sozinho se uma regra foi cumprida. Ele deve apresentar evidência produzida pelo validador ou pelo pipeline.

---

## 12. Segurança e proteção contra operações destrutivas

### 12.1 Controles P0

- secrets e webhooks fora do código;
- integração com Secret Scope, Vault ou variáveis seguras;
- proibição de credenciais em arquivos SQL e notebooks;
- proteção contra `DROP`, `TRUNCATE`, overwrite completo e delete sem filtro;
- aprovação humana para reset de checkpoint;
- aprovação humana para reset de schemaLocation;
- masking de PII em logs, alertas e ambientes não produtivos;
- classificação obrigatória do dataset.

### 12.2 Gate de mudança destrutiva

```yaml
change_risk:
  destructive_operations:
    human_approval_required: true

  operations:
    - truncate
    - drop
    - overwrite_full
    - delete_without_partition_filter
    - checkpoint_reset
    - schema_location_reset
    - revoke_grants
    - full_backfill
```

O gate não deve ser limitado ao PyODBC.

---

## 13. Classificação de dados e LGPD

Todo projeto deve declarar sua classificação.

```yaml
data_classification:
  dataset: confidential
  pii_columns:
    - cpf
    - email
    - phone

controls:
  encryption: required
  masking_non_prod: required
  logs_must_redact_pii: true
  teams_payload_must_redact_pii: true
  row_level_security: required
  retention_days: 365
  llm_usage: prohibited
```

### 13.1 Perguntas obrigatórias

- quais colunas são PII?
- dados podem ser armazenados abertos em Bronze?
- quem pode consultar cada camada?
- qual política de retenção?
- dados podem aparecer em alertas?
- podem ser utilizados por LLM?
- podem ser copiados para desenvolvimento?
- testes usam dados reais, mascarados ou sintéticos?

---

## 14. Contratos de dados

O contrato deve ser executável e versionado.

Conteúdo mínimo:

- owner;
- consumidores;
- SLA/SLO;
- schema;
- tipos;
- nulabilidade;
- chaves;
- semântica;
- classificação;
- compatibilidade;
- política de breaking change;
- versionamento;
- exemplos válidos e inválidos.

### 14.1 Versionamento

- `PATCH`: correções documentais ou regras não incompatíveis;
- `MINOR`: adição compatível;
- `MAJOR`: alteração incompatível.

### 14.2 Check automatizado

O CI deve comparar o contrato anterior com o novo e indicar:

```text
COMPATIBLE      nova coluna opcional
BREAKING        mudança string → integer
BREAKING        coluna obrigatória removida
REVIEW_REQUIRED mudança de nulabilidade
```

---

## 15. Data Quality e quarentena

A quarentena deve ser um processo operacional, não apenas uma tabela.

### 15.1 Ações permitidas por regra

- `fail_pipeline`;
- `quarantine`;
- `drop_with_metric`;
- `observe`;
- `warn`.

### 15.2 Exemplo

```yaml
data_quality_policy:
  rules:
    - id: customer_id_not_null
      severity: critical
      action: fail_pipeline

    - id: email_format
      severity: medium
      action: quarantine

    - id: description_length
      severity: low
      action: observe

  quarantine:
    owner: data-domain-team
    retention_days: 30
    reprocessing_supported: true
    max_ratio_before_failure: 0.02
    pii_allowed: false
```

### 15.3 Questões obrigatórias

- quem trata a quarentena?
- qual limite aceitável?
- quando o pipeline falha?
- como reprocessar?
- como evitar duplicação?
- qual retenção?
- PII pode ser armazenada?
- como medir backlog?

---

## 16. Schema fixo, drift e rescue

Schema fixo e rescue são compatíveis apenas quando existe uma política clara.

### 16.1 Matriz inicial

| Alteração | Bronze | Silver | Gold |
|---|---|---|---|
| Nova coluna opcional | rescue + alerta | não propagar automaticamente | não alterar |
| Nova coluna obrigatória | falhar | falhar | falhar |
| Mudança de tipo compatível | cast controlado ou rescue | aprovação | aprovação |
| Mudança de tipo incompatível | falhar | falhar | falhar |
| Remoção de coluna | alertar | falhar | falhar |
| Renome de coluna | breaking change | falhar | falhar |

### 16.2 Processo de adoção

```text
drift detectado
      ↓
rescue ou bloqueio
      ↓
alerta
      ↓
análise do owner
      ↓
atualização do contrato
      ↓
atualização do schema
      ↓
teste de compatibilidade
      ↓
promoção controlada
```

---

## 17. Idempotência, CDC e reprocessamento

Usar `MERGE`, `apply_changes` ou AUTO CDC não é suficiente para declarar um pipeline idempotente.

Todo pipeline deve declarar:

```yaml
idempotency:
  mode: merge
  business_keys:
    - customer_id
  sequencing_column: source_commit_timestamp
  deduplication_window: 7d
  late_arrival_policy: recompute
  delete_handling: soft_delete
  replay_supported: true
  source_of_truth_timestamp: commit_timestamp
```

### 17.1 Questões obrigatórias

- qual é a chave natural?
- existe uma chave técnica?
- como ordenar eventos?
- como tratar eventos atrasados?
- como tratar eventos fora de ordem?
- como detectar reenvio de arquivos?
- como reprocessar um período?
- como fazer rollback?
- como processar deletes?
- qual política de last-write-wins?

---

## 18. Retry, fail-fast e classificação de erros

`max_retries: 0` não deve ser mandato universal.

O correto é classificar a falha.

```yaml
retry_policy:
  infrastructure_transient:
    max_attempts: 3
    backoff: exponential
    jitter: true

  dependency_not_ready:
    max_attempts: 6
    backoff: fixed

  contract_violation:
    max_attempts: 0

  security_failure:
    max_attempts: 0

  deterministic_code_error:
    max_attempts: 0
```

### 18.1 Categorias mínimas

- infraestrutura transitória;
- dependência indisponível;
- erro de contrato;
- erro de schema;
- erro de DQ;
- erro de segurança;
- erro lógico determinístico;
- timeout;
- concorrência;
- limite de capacidade.

---

## 19. Observabilidade mínima

Logs JSON, Teams e freshness são necessários, mas insuficientes.

### 19.1 Contrato mínimo de telemetria

```json
{
  "run_id": "uuid",
  "pipeline": "customer_events",
  "layer": "silver",
  "status": "success",
  "rows_read": 100000,
  "rows_written": 98300,
  "rows_quarantined": 1700,
  "duplicate_rows": 250,
  "freshness_seconds": 1800,
  "duration_seconds": 240,
  "schema_version": "2.1.0",
  "data_contract_version": "3.0.0"
}
```

### 19.2 Métricas recomendadas

- registros lidos e escritos;
- registros rejeitados;
- taxa de quarentena;
- duplicados;
- watermark;
- event lag;
- processing lag;
- arquivos processados;
- arquivos ignorados;
- alteração de schema;
- duração por camada;
- custo por execução;
- custo por volume;
- tamanho de arquivos;
- skew;
- falhas por categoria;
- tempo de recuperação;
- backlog;
- consumo downstream.

---

## 20. Testes e CI

### 20.1 Pirâmide mínima

1. **Static checks**
   - secrets;
   - naming;
   - imports;
   - sintaxe;
   - operações destrutivas.

2. **Unit tests**
   - transformações;
   - regras de DQ;
   - schemas;
   - funções utilitárias.

3. **Contract tests**
   - colunas;
   - tipos;
   - nulabilidade;
   - chaves;
   - compatibilidade.

4. **Integration tests**
   - Delta;
   - Unity Catalog;
   - checkpoint;
   - DAB;
   - permissões.

5. **Data tests**
   - volumes;
   - duplicação;
   - reconciliação;
   - regras de negócio.

6. **Operational tests**
   - retry;
   - alertas;
   - falha;
   - recuperação;
   - replay.

7. **Deployment tests**
   - bundle validate;
   - deploy em ambiente temporário;
   - smoke test;
   - rollback.

### 20.2 Pipeline CI mínimo

```text
lint
  ↓
static security checks
  ↓
unit tests
  ↓
contract compatibility
  ↓
architecture checks
  ↓
bundle or DAG validation
  ↓
integration smoke test
  ↓
compliance report
```

---

## 21. Estratégia DLT legado e SDP moderno

O canônico precisa declarar o ciclo de vida das tecnologias.

```yaml
technology_policy:
  new_projects:
    databricks_pipeline_api: sdp

  brownfield_projects:
    dlt_legacy:
      supported: true
      migration_required: false
      modernization_assessment: required

  generated_examples:
    default: sdp
    legacy_examples: allowed_with_marker
```

### 21.1 Regras iniciais

- projetos novos Databricks devem preferir SDP;
- DLT legado continua suportado em brownfield;
- migração não deve ser automática sem avaliação;
- o agente deve produzir relatório de compatibilidade;
- checkpoints e estado precisam ser preservados;
- rollback deve existir antes da migração.

---

## 22. Exceções e waivers

Toda regra bloqueante que permita exceção deve ter um processo formal.

```yaml
waiver:
  rule_id: DQ-M03
  project: legacy-customer-pipeline
  reason: Fonte não permite separar inválidos neste momento
  owner: data-platform
  approved_by: architecture-board
  expiration: 2026-12-31
  remediation_plan: Implementar quarentena na migração SDP
```

### 22.1 Regras para waiver

- deve ter prazo de expiração;
- deve ter owner;
- deve ter justificativa;
- deve ter aprovador;
- deve ter plano de correção;
- deve aparecer no relatório de CI;
- não pode ser aplicado silenciosamente por um agente.

---

## 23. Estratégia para projetos existentes

Projetos brownfield não devem ser obrigados a corrigir toda dívida imediatamente.

### 23.1 Modos de operação

#### Audit

Apenas identifica problemas.

#### Baseline

Registra a dívida atual.

#### Ratchet

Impede que a dívida aumente.

#### Full enforcement

Aplica todas as regras definidas para o perfil.

### 23.2 Exemplo de ratchet

```text
Baseline:
- 2 secrets hardcoded
- 14 tabelas sem lineage
- 8 pipelines sem testes

Novo PR:
- adicionou 1 tabela sem lineage

Resultado: BLOQUEADO
Motivo: aumento da dívida técnica existente
```

---

## 24. Scaffolds iniciais

Não tentar cobrir todas as arquiteturas na primeira versão.

### 24.1 Scaffold A — Databricks moderno

```text
Databricks + DAB + SDP + Unity Catalog
```

Deve conter:

- `databricks.yml`;
- resources;
- Bronze, Silver e Gold;
- contrato;
- schema;
- DQ;
- quarentena;
- observabilidade;
- testes;
- CI;
- deploy;
- runbooks.

### 24.2 Scaffold B — On-premises

```text
Spark on YARN + Airflow + ADLS
```

Deve conter:

- `config/`;
- `etl/`;
- `pipelines/`;
- DAG fina;
- spark-submit;
- contrato;
- validação;
- observabilidade;
- testes;
- CI;
- runbooks.

---

## 25. Separação de responsabilidade no código

O scaffold deve evitar notebooks e scripts monolíticos.

Estrutura conceitual:

```text
src/<package>/
├── config/
├── schemas/
├── contracts/
├── ingestion/
├── transformations/
├── expectations/
├── quarantine/
├── observability/
├── alerts/
├── operations/
└── pipelines/
```

Princípio:

> Schema, regras de qualidade, configuração, alertas, contrato medalhão e orquestração devem ser responsabilidades separadas.

---

## 26. Skills candidatas — somente após o kernel

### 26.1 P0

- validar secrets;
- classificar dados;
- detectar operação destrutiva;
- validar contrato mínimo;
- validar metadados de lineage;
- validar IaC de job;
- validar existência de testes.

### 26.2 P1

- gerar contrato de dados;
- gerar schema explícito;
- implementar DQ e quarentena;
- implementar schema drift;
- implementar telemetria mínima;
- implementar política de retry;
- implementar idempotência declarada.

### 26.3 P2

- scaffold DAB + SDP;
- scaffold Spark + Airflow;
- converter notebook monolítico em módulos;
- gerar runbooks;
- gerar dashboards operacionais;
- avaliar migração DLT → SDP.

---

## 27. Agentes candidatos — somente após regras e checks

| Agente | Responsabilidade |
|---|---|
| `pipeline-architect` | selecionar perfil e arquitetura |
| `data-contracts-engineer` | gerar e validar contratos |
| `data-quality-agent` | definir regras, quarentena e thresholds |
| `schema-drift-agent` | classificar e tratar drift |
| `observability-agent` | implementar métricas e alertas |
| `security-reviewer` | validar secrets, PII e operações destrutivas |
| `pipeline-reviewer` | executar lanes de revisão com evidência |
| `migration-agent` | avaliar DLT → SDP ou legado → canônico |
| `airflow-builder` | criar DAG fina para perfil on-premises |
| `sdp-builder` | criar pipelines Databricks modernos |

### 27.1 Regra para agentes

Os agentes devem consumir as mesmas regras usadas pelo CI.

```text
YAML normativo
     ↓
validator
     ↓
CI
     ↓
agentes
     ↓
documentação
```

---

## 28. Pipeline Review revisado

O review deve trabalhar com lanes verificáveis.

### 28.1 Lanes propostas

1. perfil arquitetural;
2. contrato de dados;
3. schema e compatibilidade;
4. medalhão e responsabilidades;
5. qualidade e quarentena;
6. idempotência e CDC;
7. observabilidade;
8. segurança e LGPD;
9. orquestração e deploy;
10. testes e CI;
11. operação, retry e rollback;
12. performance e custo;
13. documentação e ownership.

### 28.2 Saída esperada

```text
Architecture      PASS
Contracts         FAIL  DC-M02
Data Quality      WARN  DQ-R04
Security          FAIL  SEC-M01
Observability     WAIVED OBS-M02
Operations        PASS
```

---

## 29. Priorização revisada

### P0 — Segurança, integridade e enforcement mínimo

- fonte normativa única;
- schema das regras;
- scanner de secrets;
- gate destrutivo;
- classificação de dados;
- owner e metadados mínimos;
- CI básico;
- baseline brownfield;
- geração `.claude/` e `.cursor/`.

### P1 — Qualidade operacional

- contratos;
- testes de contrato;
- DQ;
- quarentena;
- schema drift;
- freshness;
- telemetria;
- classificação de erros;
- retry.

### P2 — Padronização arquitetural

- scaffold Databricks SDP;
- scaffold Spark/Airflow;
- DAB;
- naming;
- separação SOLID;
- runbooks;
- documentação operacional.

### P3 — Modernização e otimização

- migração DLT → SDP;
- Liquid Clustering;
- system tables;
- SQL Alert v2;
- Lakehouse Monitors;
- FinOps;
- expansão de perfis.

---

## 30. Piloto recomendado

O primeiro piloto brownfield deve ser o projeto `dtbks-auditoria`.

Motivos:

- possui produto real;
- possui documentação e inventário;
- possui gaps conhecidos;
- contém DLT legado;
- possui dados sensíveis;
- possui alertas Teams;
- possui jobs criados fora do bundle;
- permite testar baseline e ratchet.

### 30.1 Objetivos do piloto

1. verificar se os checks detectam os gaps conhecidos;
2. medir falsos positivos;
3. gerar baseline;
4. impedir novas regressões;
5. validar waivers;
6. testar correções propostas pelos agentes;
7. medir esforço de adoção;
8. ajustar severidades antes de expandir.

### 30.2 O que o piloto não deve fazer inicialmente

- migrar todo DLT para SDP;
- corrigir toda dívida de uma vez;
- reescrever todos os pipelines;
- bloquear produção sem baseline;
- gerar automaticamente mudanças destrutivas.

---

## 31. Definition of Done da primeira versão

A primeira versão do canônico só deve ser considerada pronta quando:

- [ ] existir fonte normativa única;
- [ ] regras possuírem categoria, severidade e aplicabilidade;
- [ ] `.claude/` e `.cursor/` forem gerados automaticamente;
- [ ] existir CLI de validação;
- [ ] existir relatório JSON e Markdown;
- [ ] existir scanner de secrets;
- [ ] existir gate de operação destrutiva;
- [ ] existir baseline brownfield;
- [ ] existir processo de waiver;
- [ ] existir um scaffold Databricks;
- [ ] existir um scaffold on-premises;
- [ ] existir CI mínimo;
- [ ] existir piloto executado no `dtbks-auditoria`;
- [ ] agentes apresentarem evidência e não apenas opinião;
- [ ] falsos positivos terem sido medidos;
- [ ] documentação humana refletir as regras executáveis.

---

## 32. Decisões obrigatórias antes do build

1. O canônico será multiplataforma desde o início?
2. Quais perfis entram na versão 1?
3. Quais regras serão universais?
4. Quais regras serão bloqueantes?
5. Quem aprova waivers?
6. Qual será a tecnologia da CLI de validação?
7. Onde ficará a fonte normativa?
8. Novos projetos Databricks usarão SDP por padrão?
9. DLT legado será apenas suportado ou também migrado?
10. Qual será a política para dados sensíveis em Bronze?
11. Quais operações exigem aprovação humana?
12. Como CI e agentes compartilharão as mesmas regras?
13. Qual será o baseline inicial do projeto piloto?
14. Quais métricas definirão sucesso do piloto?

---

## 33. Métricas de sucesso

### 33.1 Qualidade do canônico

- percentual de regras verificáveis automaticamente;
- taxa de falsos positivos;
- taxa de falsos negativos conhecidos;
- tempo de execução dos checks;
- número de waivers ativos;
- idade média dos waivers;
- divergência entre `.claude/` e `.cursor/`;
- percentual de projetos com perfil declarado.

### 33.2 Adoção

- projetos novos usando scaffold;
- projetos existentes com baseline;
- PRs bloqueados por regressão real;
- tempo médio para corrigir falha;
- percentual de contratos versionados;
- percentual de pipelines com telemetria mínima;
- percentual de pipelines com owner definido.

### 33.3 Operação

- redução de secrets em código;
- redução de falhas por schema drift;
- redução de incidentes sem alerta;
- redução de cargas não idempotentes;
- redução de pipelines criados apenas pela UI;
- redução do tempo de diagnóstico.

---

## 34. Riscos da iniciativa

| Risco | Mitigação |
|---|---|
| excesso de regras | perfis e aplicabilidade condicional |
| muitos falsos positivos | piloto, baseline e ajuste de severidade |
| baixa adoção | modo audit e ratchet antes de bloqueio total |
| duplicidade Claude/Cursor | geração automática por adapters |
| agentes inventarem conformidade | exigir evidência do validator |
| lock-in Databricks | separar regras universais de regras de plataforma |
| quarentena virar depósito | ownership, SLA, retenção e reprocessamento |
| waivers permanentes | expiração e relatório de dívida |
| modernização quebrar legado | política DLT/SDP e rollback |
| CI lento | checks por estágio e execução condicional |

---

## 35. Resultado esperado

Ao final da evolução, o harness canônico não deve ser apenas uma biblioteca de conhecimento.

Ele deve funcionar como uma camada integrada de:

```text
orientação
+ geração
+ validação
+ evidência
+ governança
+ operação
```

O fluxo ideal será:

```text
usuário descreve o pipeline
        ↓
agente seleciona o perfil
        ↓
scaffold é gerado
        ↓
contratos e políticas são definidos
        ↓
código é implementado
        ↓
checks determinísticos são executados
        ↓
agente corrige falhas permitidas
        ↓
CI valida
        ↓
humano aprova riscos relevantes
        ↓
deploy reproduzível
        ↓
telemetria e operação contínua
```

---

## 36. Conclusão

O maior valor do novo canônico não será a quantidade de agentes, skills ou KBs.

Será a capacidade de transformar princípios de Engenharia de Dados em controles que possam ser:

- aplicados conforme o perfil do projeto;
- verificados automaticamente;
- explicados ao desenvolvedor;
- auditados;
- excepcionados formalmente;
- evoluídos sem quebrar projetos existentes.

O princípio final é:

> **Nenhum mandato deve existir apenas como prosa quando puder ser convertido em regra executável, evidência objetiva ou gate de engenharia.**

---

## 37. Próxima ação recomendada

Antes de criar skills ou agentes adicionais, produzir os seguintes artefatos:

```text
01-rule-schema.yaml
02-architecture-profiles.yaml
03-severity-policy.yaml
04-waiver-policy.yaml
05-brownfield-policy.yaml
06-technology-lifecycle.yaml
07-canonical-data-check-design.md
08-pilot-dtbks-auditoria.md
```

Somente depois desses artefatos aprovados deve começar a implementação do kernel executável e dos scaffolds.

---

**Fim do sketch revisado.**
