# Encaixe por Perfil de Carga de Trabalho

Nenhuma plataforma é universalmente melhor — o encaixe depende do perfil de workload, do time e
do que já existe no stack. Esta comparação é **trade-off**, não recomendação única.

## Snowflake tende a se encaixar melhor quando

- Workload é predominantemente **SQL analytics e BI** (dashboards, relatórios, self-service
  analytics para usuários de negócio).
- Múltiplos times/departamentos precisam consultar os mesmos dados concorrentemente sem
  contenção — isolamento de compute por warehouse resolve isso de forma simples.
- **Data sharing** entre organizações ou entre contas é um requisito (Snowflake Marketplace /
  Secure Data Sharing são nativos e fortes nesse ponto).
- O time é majoritariamente analista/SQL-first, sem forte necessidade de notebooks, ML nativo ou
  processamento de streaming complexo.
- Simplicidade operacional é prioridade — menos superfícies de configuração que Databricks.

## Databricks tende a se encaixar melhor quando

- Workload combina **engenharia de dados + ciência de dados/ML** no mesmo pipeline (ex: feature
  engineering, treino de modelo, deploy, tudo no mesmo ambiente com MLflow).
- Há necessidade de **processamento em escala com Spark** (transformações complexas, joins
  pesados, streaming com Structured Streaming) além de SQL puro.
- O time já usa notebooks (Python/Scala/R) como unidade de trabalho principal, não só SQL.
- Portabilidade de formato de dados importa — Delta Lake aberto evita lock-in de formato,
  relevante para orgs com estratégia multi-plataforma ou requisito de auditoria de dados fora da
  plataforma.
- Streaming em tempo real com a mesma infraestrutura de batch (arquitetura lambda/kappa
  simplificada via DLT).

## BigQuery tende a se encaixar melhor quando

- A org já está no **ecossistema Google Cloud** (GA4, Google Ads, Looker, Firebase) — integração
  nativa reduz fricção de ingestão.
- Workload é **analytics ad-hoc de alto volume, baixa frequência de operação** — serverless
  elimina o overhead de gerenciar cluster/warehouse para queries esporádicas.
- Time pequeno sem capacidade de operar infraestrutura — zero-ops é vantagem decisiva.
- Precisa de ML simples direto em SQL (BigQuery ML) sem montar pipeline de MLOps completo.
- Escala extrema de leitura esporádica (ex: consultas analíticas em PBs de dados, poucas vezes
  por dia) — modelo on-demand favorece uso irregular.

## Quando o perfil é misto

Times grandes frequentemente usam mais de uma plataforma por camada: ex. Databricks para
engenharia/ML na camada Bronze/Silver e Snowflake ou BigQuery para servir Gold a analistas de
BI — não é incomum nem "errado" combinar, desde que o custo de manter duas plataformas seja
justificado pelo ganho de encaixe em cada camada.

## Gotchas

- Escolher plataforma pelo hype do time (ex: "todo mundo usa Databricks para ML") sem considerar
  que 80% do workload real é SQL analytics simples gera overhead operacional desnecessário.
- Escolher BigQuery só pela simplicidade sem modelar o padrão de scan das queries mais comuns
  pode resultar em custo on-demand imprevisível — validar com estimativa de bytes escaneados
  antes de comprometer.
- Ignorar o skillset do time existente: migrar um time SQL-first para Databricks sem investimento
  em treinamento de Spark/Python gera fricção que anula o ganho arquitetural.
