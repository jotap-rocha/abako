# Medallion SDD Gates — checklist de entrada para pipelines

## Âncora normativa

- **Escopo:** processo SDD (`harness-brainstorm`, `harness-define`) e Dev Loop (`prompt-crafter`).
- **Não substitui** checks mecânicos DE (`data-engineering.yaml`) — guia **perguntas** antes de implementar.
- **Implementação Silver:** após gates, use [silver-checklist-odcs.md](silver-checklist-odcs.md).
- **Arquitetura:** [medallion.md](../concepts/medallion.md) · contratos: [data-contracts.md](../concepts/data-contracts.md).

## Quando acionar

| Fluxo | Gatilho |
|---|---|
| SDD `/novo-projeto` | Tipo **b** (Spark local), **c** (Databricks) ou **e** com escopo pipeline/medallion |
| SDD `/novo-projeto` | Após gate **4a** (runtime humano) e **4a-bis** (AI-DEV-KIT se Databricks) |
| SDD evolução | Projeto existente alterando bronze/silver/gold/raw |
| Dev Loop `/dev` | Descrição menciona pipeline, medallion, bronze, silver, gold, ingestão, DLT, Spark |

**Hard-stop SDD:** não avance para `harness-define` / PRD sem **tabelas listadas** **ou** amostra
(DDL, arquivo, tabela UC, paste na janela).

**Dev Loop:** escopo > 1 camada ou greenfield → redirecione para `/novo-projeto`.

## Modelo de camadas (referência)

```text
Raw → Bronze (JSON fiel + lineage) → Silver (normalizado + contrato ODCS)
    → Gold (analítico, subset negócio) → Diamond (multidimensional — fora deste gate)
```

| Camada | Contrato | Lineage mínimo |
|---|---|---|
| Raw | Nenhum | `_source_file`, `_ingest_ts` |
| Bronze | **Ingestão** (schema-fonte; struct/array OK) | + `_source_system`, `_ingested_at`, `_source`, `_run_id`, `_batch_id` |
| Silver | **ODCS** (flat, sem multivalor) | + `_processed_at`, `_pipeline_version`; propaga `_source_system` |
| Gold | **Consumo** (colunas de negócio + descrições) | + `_updated_at` |

## Gate transversal (todas as camadas)

Preencher **antes** de sair do brainstorm ou craft Dev Loop:

| # | Pergunta | Obrigatório |
|---|---|---|
| T1 | Quais **entidades/tabelas** entram no escopo? | Sim |
| T2 | Quais **colunas** por entidade — ou amostra (arquivo/DDL/tabela/paste)? | Sim |
| T3 | `_source_system` por entidade (sistema de negócio: ERP, CRM, API-X)? | Sim |
| T4 | Formato-fonte: JSON / CSV / Parquet / API / outro? | Sim |
| T5 | Camada-alvo deste SDD/Dev Loop: Raw / Bronze / Silver / Gold / multi? | Sim |
| T6 | Escopo multi-camada (>1)? Recomendar **SDDs separados** por camada. | Se multi |
| T7 | JSON com **struct/array** aninhados? | Se JSON |
| T8 | Consumo final inclui **Genie / sala NL** além de BI/dashboard? | Sim |

### Amostra de dados (T2)

Aceite **um** dos modos:

1. Lista explícita de colunas + tipos esperados
2. Agente lê arquivo no repo (`data/landing/*.json`, etc.)
3. Agente lê DDL ou schema de tabela existente
4. Usuário cola amostra JSON/CSV na janela de contexto

Sem T1+T2 → **pare** e colete antes de `01-grill.md` ou PROMPT final.

## Gate Bronze

| # | Pergunta |
|---|---|
| B1 | JSON aninhado permanece **fiel** na Bronze (sem explode/flatten)? |
| B2 | Contrato de **ingestão** versionado (`contracts/{entity}-source-vN.yaml`)? |
| B3 | Política schema rescue documentada (`fail` vs `quarantine`)? |
| B4 | `_source_system` definido por entidade? |

**Proibido na Bronze:** regras de negócio, filtrar inválidos silenciosamente, normalizar arrays/structs.

## Gate Silver

| # | Pergunta |
|---|---|
| S1 | Mapeamento explode/flatten: qual array/struct vira quais colunas flat? |
| S2 | Contrato **ODCS** Silver (`contracts/{entity}-vN.yaml`) linkado ao contrato Bronze via `source_contract_id`? |
| S3 | Padrão de nomes: snake_case, PT-BR, `display_name` para LLM? |
| S4 | Política de ausentes: NULL string vs sentinel (1970, zero) — **por campo no contrato**? |
| S5 | TRIM/LTRIM/RTRIM em strings de identificação? |
| S6 | Capitalização no **valor** (`initcap`) — quais colunas? |
| S7 | Inferência implícita: CPF, telefone, CEP, UF — quais campos? |
| S8 | Severidade por regra: `fail` \| `quarantine` \| `log` (ver silver-checklist)? |

**Proibido na Silver:** cast primário de tipo (Bronze), ingestão Raw, agregações Gold, `SELECT *`, colunas multivaloradas.

## Gate Gold + NL (Genie)

| # | Pergunta |
|---|---|
| G1 | Quais colunas são **relevantes para negócio** (subset analítico)? |
| G2 | Consumidores: BI, ad-hoc, ML, **Genie/NL**? |
| G3 | Descrição de **tabela** e **coluna** (comments UC / glossary)? |
| G4 | Relacionamentos: PK/FK técnico **ou** negócio (titular/beneficiário, cliente/vendedor)? |
| G5 | Necessita **camada semântica** (métricas, sinônimos, unidades)? |
| G6 | Necessita **ontologia** (conceitos de domínio, hierarquias)? |
| G7 | Governança: owner, classificação, política de acesso UC? |

Gold analítico precede camada **Diamond** (multidimensional) — não confundir agregação dimensional com subset exploratório.

## Contrato dual (mercado)

| Camada | Tipo | Conteúdo |
|---|---|---|
| Bronze | Ingestão / source | Schema-fonte, struct/array permitidos, `ingestion_mode`, drift policy |
| Silver | ODCS completo | Flat, quality, SLA, versioning — gate mecânico `DE-B003` |
| Gold | Consumo (opcional) | Colunas expostas, descrições, relationships para NL |

Tipagem de negócio e contrato **prescritivo** ficam na **Silver**; Bronze documenta o que **chegou**.

## SDD por camada (recomendado)

Escopo multi-camada → **3 SDDs** (branches separadas):

1. `feat/{projeto}-bronze` — ingestão, lineage, contrato fonte
2. `feat/{projeto}-silver` — normalização JSON, ODCS, qualidade
3. `feat/{projeto}-gold` — subset analítico, Genie, semântica

Cada SDD repete gate transversal (T1–T8) filtrado pela camada-alvo.

## Dev Loop — seção PROMPT

Ao gerar `PROMPT_*.md` para tarefa de pipeline, incluir:

```markdown
## Medallion Context (capturado no craft)
- Camada-alvo:
- Entidades/tabelas:
- _source_system:
- Formato-fonte / JSON aninhado:
- Colunas ou amostra:
- Contrato (ingestão / ODCS / N/A):
- Genie/NL:
```

## Ver também

- [silver-checklist-odcs.md](silver-checklist-odcs.md) — implementação Silver pós-gate
- [genie-readiness.md](genie-readiness.md) — checklist NL/Genie (gate T8=sim)
- [gold-analytic.md](../concepts/gold-analytic.md) — camada Gold analítica
- [data-lineage.md](../concepts/data-lineage.md) — colunas `_source_system`
- [quarantine.md](../concepts/quarantine.md) — destino de inválidos
- Agents: `harness-brainstorm`, `harness-define`, `prompt-crafter`
