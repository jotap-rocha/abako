# Arquiteturas — Snowflake vs Databricks vs BigQuery (alto nível)

## Snowflake — multi-cluster shared data architecture

Três camadas desacopladas:
1. **Storage layer** — dados armazenados em formato colunar proprietário, comprimidos,
   organizados em micro-partitions (~50-500MB cada) com metadados automáticos (min/max por
   coluna) usados para pruning.
2. **Compute layer** — virtual warehouses independentes, cada um lê o mesmo storage layer sem
   competir por recursos entre si (isolamento de workload nativo).
3. **Cloud services layer** — metadata, otimização de query, controle de acesso, gerência de
   transações — orquestra as outras duas camadas, não é billable diretamente.

Roda sobre AWS, Azure ou GCP (a Snowflake abstrai o cloud provider — o usuário escolhe a região,
não gerencia infra).

## Databricks — Lakehouse sobre Delta Lake

Combina a flexibilidade de data lake (armazenamento aberto, barato, em formato open-source) com
garantias de data warehouse (ACID transactions, schema enforcement) via **Delta Lake** (formato
de tabela open-source baseado em Parquet + transaction log).

- **Data plane**: clusters Spark rodam na conta cloud do próprio cliente (AWS/Azure/GCP) — o
  cliente mantém mais controle/visibilidade da infra subjacente que em Snowflake ou BigQuery.
- **Control plane**: gerenciado pela Databricks (notebooks, jobs, MLflow, Unity Catalog).
- **Unity Catalog**: camada de governança unificada — permissões, lineage, discovery — cobrindo
  tabelas, arquivos, modelos ML e features num único namespace.
- Suporta múltiplas linguagens/engines no mesmo lakehouse: SQL, PySpark, Scala, MLlib, além de
  Delta Live Tables (DLT) para pipelines declarativos.

## BigQuery — serverless, arquitetura Dremel

- **Totalmente serverless** — não há cluster para provisionar, redimensionar ou gerenciar; o
  usuário escreve SQL e o Google gerencia a infraestrutura de execução por trás.
- Baseado internamente em **Dremel** — motor de execução de query colunar e distribuído que
  separa storage (Colossus, o sistema de arquivos distribuído do Google) de compute (o motor de
  execução que aloca slots dinamicamente).
- Integração nativa com o ecossistema Google Cloud: BigQuery ML (treinar modelos via SQL),
  BigQuery Omni (query em dados fora do GCP), integração direta com Looker/Looker Studio.
- Não há conceito de "cluster" visível ao usuário — a unidade operacional é a query e o slot.

## Trade-off de modelo operacional

| Dimensão | Snowflake | Databricks | BigQuery |
|---|---|---|---|
| Gerência de infra | Nenhuma (full-managed, multi-cloud) | Parcial (cliente controla cluster/VPC) | Nenhuma (full-managed, GCP nativo) |
| Formato de dados | Proprietário (interno) | Aberto (Delta/Parquet) | Proprietário (interno, com export para Parquet/Avro) |
| Portabilidade de dados | Baixa (formato fechado, export explícito) | Alta (Delta Lake é padrão aberto, sem vendor lock-in no formato) | Baixa (formato fechado) |
| Caso de uso nativo forte | SQL analytics, BI, data sharing entre orgs | ML/Data Science + Engenharia de dados unificada | Analytics ad-hoc em escala com zero ops |
| Multi-cloud | Sim (AWS/Azure/GCP, mesma experiência) | Sim (AWS/Azure/GCP, mas com nuances por cloud) | Não (GCP nativo; BigQuery Omni estende leitura, não é multi-cloud pleno) |

## Gotchas

- Lock-in de formato de dados é mais crítico em Snowflake e BigQuery (formato proprietário) do
  que em Databricks (Delta Lake é aberto — dá para ler os arquivos Parquet mesmo fora da
  plataforma).
- Databricks exige mais decisões operacionais do cliente (VPC, IAM, network policies) porque o
  data plane roda na conta cloud do cliente — isso é vantagem de controle e desvantagem de
  complexidade operacional, dependendo do time.
- BigQuery não tem "warehouse" nem "cluster" para nomear/isolar workloads da mesma forma que
  Snowflake — isolamento de workload em BigQuery é feito via reservations de slots, não via
  múltiplos warehouses nomeados.
