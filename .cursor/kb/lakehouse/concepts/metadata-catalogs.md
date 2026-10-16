---
topic: metadata-catalogs
confidence: null
mcp_validated: null
---

# Catálogo de Metadados: Unity Catalog vs Iceberg REST Catalog vs Glue

## O que um catálogo faz

Resolve `namespace.table` → localização física + snapshot atual. É o ponto de coordenação que
garante que múltiplos writers não corrompam a tabela (commit atômico via compare-and-swap do
ponteiro de snapshot) e que múltiplos engines vejam o mesmo estado. Sem catálogo compartilhado,
"open table format" não é multi-engine na prática — cada motor teria sua própria visão do
snapshot atual.

Três responsabilidades centrais: **descoberta** (listar tabelas/schemas), **coordenação
transacional** (commit atômico do ponteiro de metadata), **controle de acesso** (quem lê/escreve
o quê).

## Comparação

| Dimensão | Unity Catalog | Iceberg REST Catalog | AWS Glue Data Catalog |
|---|---|---|---|
| Vendor | Databricks (open-sourced parcialmente em 2024) | Especificação aberta (Apache Iceberg) | AWS-nativo |
| Formatos suportados | Delta nativo; Iceberg via UniForm/leitura direta | Iceberg (é a spec de referência do formato) | Hive Metastore-compatível — Iceberg, Delta (via manifest), Hudi |
| Modelo de acesso | RBAC + ABAC (tags), lineage automático, row/column-level security | Depende da implementação (Nessie, Polaris, Tabular, Lakekeeper, S3 Tables) | IAM policies (nível de tabela/DB, não linha/coluna nativamente) |
| Portabilidade entre clouds | Databricks-managed ou self-hosted (OSS UC Server) | Alta — spec vendor-neutral, várias implementações | Baixa — acoplado a AWS |
| Versionamento de catálogo (branch/tag de tabela) | Parcial | Nativo em implementações como Nessie (Git-like) | Não |
| Caso de uso típico | Governança centralizada em ambiente Databricks/lakehouse multi-workspace | Multi-engine sem lock-in de vendor (Spark + Trino + Flink + Snowflake lendo o mesmo catálogo) | Pipelines já no ecossistema AWS (Athena, EMR, Redshift Spectrum) |

## Como escolher

1. **Já opera em Databricks e a maioria dos consumidores é Databricks/Spark** → Unity Catalog.
2. **Múltiplos engines de vendors diferentes precisam do mesmo catálogo, sem lock-in** → Iceberg
   REST Catalog (implementações: Nessie, Apache Polaris, Lakekeeper, AWS S3 Tables).
3. **Stack 100% AWS com Athena/EMR/Redshift Spectrum já consumindo Hive Metastore** → Glue Data
   Catalog — migração mais barata, mas menor portabilidade futura.

## Gotchas

- **Glue não é transacional por si só**: Glue Data Catalog é metastore compatível com Hive; a
  atomicidade do commit vem do formato de tabela (Iceberg/Delta) e não do catálogo — sem formato
  aberto por cima, Glue sozinho não dá ACID.
- **Unity Catalog + Iceberg**: leitura direta de tabelas Iceberg é suportada, mas escrita nativa
  multi-engine (não-Databricks) via UC ainda depende da versão/edição — validar antes de assumir
  paridade total com REST catalog puro.
- **Trocar de catálogo não é trivial**: migrar de Hive Metastore/Glue para um REST catalog exige
  reescrever ou registrar (`register_table`) os metadados existentes — não é só mudar uma
  connection string.
