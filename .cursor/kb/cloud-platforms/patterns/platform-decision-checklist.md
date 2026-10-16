# Checklist de Decisão — Escolher Plataforma de Dados em Nuvem

Processo estruturado para decidir entre Snowflake, Databricks e BigQuery dado um conjunto de
requisitos. **Não existe resposta certa universal** — o objetivo é tornar o trade-off explícito
e auditável (registrar como ADR quando a decisão for de arquitetura, ver
`.claude/rules/definicao-de-pronto.md`).

## Passo 1 — Levantar requisitos

| Pergunta | Por que importa |
|---|---|
| Workload é majoritariamente SQL/BI ou inclui ML/engenharia pesada? | Direciona para Snowflake/BigQuery (SQL-first) vs Databricks (unificado) |
| Time já domina qual stack (SQL puro, Spark/Python, ou nenhum)? | Custo de aprendizado é real e afeta velocidade de entrega |
| Já existe cloud provider dominante na org (AWS/Azure/GCP)? | BigQuery é GCP-nativo; Snowflake/Databricks são multi-cloud |
| Formato de dados precisa ser aberto/portável (evitar lock-in)? | Databricks (Delta Lake) é o único com formato aberto nativo |
| Volume e padrão de consulta (contínuo vs esporádico)? | Direciona compute reservado (warehouse/DBU) vs on-demand (BigQuery) |
| Necessidade de data sharing externo (parceiros, clientes)? | Snowflake tem Secure Data Sharing/Marketplace mais maduro |
| Necessidade de streaming em tempo real integrado ao batch? | Databricks (Structured Streaming + DLT) tem vantagem nativa |
| Orçamento: previsibilidade de custo é crítica ou elasticidade importa mais? | Slots/warehouse fixo = previsível; on-demand = elástico mas variável |

## Passo 2 — Decision tree

```
Requisito dominante do workload?
    │
    ├── SQL analytics + BI, múltiplos times concorrentes ─────► Snowflake
    │     (isolamento de warehouse, data sharing forte)
    │
    ├── ML + Engenharia de dados no mesmo pipeline ────────────► Databricks
    │     (lakehouse unificado, MLflow, Delta Lake aberto)
    │
    ├── Já é GCP-nativo, quer zero-ops, workload irregular ────► BigQuery
    │     (serverless, integração GA4/Ads/Looker)
    │
    └── Workload misto (ML + BI + volumes distintos por camada)?
          └── Considerar combinação: Databricks (Bronze/Silver + ML)
              + Snowflake/BigQuery (Gold + BI) — avaliar custo de
              manter 2 plataformas vs ganho de encaixe por camada
```

## Passo 3 — Matriz de pontuação (exemplo, adaptar pesos ao contexto)

| Critério | Peso | Snowflake | Databricks | BigQuery |
|---|---|---|---|---|
| Fit com SQL/BI | Alto se workload é analytics | Forte | Médio | Forte |
| Fit com ML/Data Science | Alto se há time de ML | Fraco (via partners/Snowpark) | Forte (nativo) | Médio (BigQuery ML, limitado) |
| Portabilidade de dados | Alto se lock-in é preocupação de governança | Fraco (proprietário) | Forte (Delta aberto) | Fraco (proprietário) |
| Zero-ops | Alto se time é pequeno | Médio (sem infra, mas warehouse sizing manual) | Fraco (cluster/VPC exige operação) | Forte (serverless total) |
| Previsibilidade de custo | Alto se orçamento é rígido | Forte (warehouse fixo) | Médio (autoscaling varia) | Fraco on-demand / Forte com slots |
| Multi-cloud | Alto se estratégia é multi-cloud | Forte | Forte | Fraco (GCP nativo) |

Pontue cada célula (ex: Forte=3, Médio=2, Fraco=1), multiplique pelo peso do critério para o
contexto específico, some por coluna — a maior pontuação **não decide sozinha**, é insumo para
discussão com stakeholders técnicos e de negócio.

## Passo 4 — Validar com prova de conceito (PoC), não só na planilha

Antes de comprometer, rodar PoC com dados/queries reais (não sintéticos) por 2-4 semanas:
1. Migrar um subconjunto representativo de dados (inclui o pior caso: maior tabela, query mais
   pesada).
2. Medir custo real (não estimado) rodando a carga de um período real (ex: 1 semana de produção
   espelhada).
3. Medir latência ponta-a-ponta do caso de uso mais crítico, não só a query isolada.
4. Envolver o time que vai operar no dia a dia — fit de ferramenta inclui fit de fricção humana.

## Passo 5 — Registrar a decisão

Se a escolha de plataforma é uma decisão de arquitetura (é, quase sempre) — registrar ADR em
`docs/adr/` com: requisitos levantados, alternativas consideradas, trade-offs explícitos,
critério de reversão (o que faria a org trocar de plataforma no futuro).

## Gotchas

- Decidir só pela pontuação numérica sem PoC real é o erro mais comum — custo estimado em
  planilha raramente bate com custo real de produção (padrões de query variam mais do que se
  imagina).
- Ignorar o custo de migração de dados/pipelines existentes ao comparar "custo mensal" das
  plataformas — o TCO inclui a migração, não só a operação steady-state.
- Escolher com base em benchmark público (TPC-DS/TPC-H) sem validar que o benchmark reflete o
  padrão de query real da organização — benchmarks de vendor tendem a favorecer o cenário em que
  a própria plataforma performa melhor.
