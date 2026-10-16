# Arquitetura Medallion

## O que é

Padrão de organização de dados em camadas progressivas de qualidade.
Cada camada tem uma responsabilidade única e imutável.

## As 4 camadas

### Raw (Zona de Pouso)
- **Responsabilidade**: cópia exata da fonte, imutável, nunca transformada
- **Nunca fazer**: transformar, filtrar, renomear, deletar
- **Formato**: preservar o original (CSV, JSON, Parquet, etc.)
- **Colunas obrigatórias adicionadas**: `_source_file`, `_ingest_ts`
- **Retenção**: permanente (é o backup de disaster recovery)

### Bronze (Landing tipado / forma-fonte)
- **Responsabilidade**: preservar forma-fonte (incl. JSON struct/array) + metadados de lineage. Sem lógica de negócio.
- **Nunca fazer**: aplicar regras de negócio, filtrar registros "ruins", explode/flatten de aninhados
- **Formato**: Delta Lake (ou Parquet com schema enforcement)
- **Colunas obrigatórias**: `_ingested_at`, `_source`, `_source_system`, `_run_id`, `_batch_id`
- **JSON aninhado**: manter struct/array **como veio**; normalização só na Silver
- **Contrato**: ingestão / schema-fonte (leve) — ver [data-contracts.md](data-contracts.md)
- **Schema evolution**: configurado aqui (merge/quarantine/fail)

### Silver (Dados Limpos e Validados)
- **Responsabilidade**: normalizar JSON (explode/flatten), deduplicação, validação, limpeza
- **Nunca fazer**: agregar, fazer join com tabelas de negócio externas ao domínio, colunas multivaloradas
- **Formato**: Delta Lake com schema enforcement estrito
- **Colunas obrigatórias**: `_processed_at`, `_pipeline_version`, `_source_system` (propagado)
- **Contrato**: ODCS completo (flat) — gate `DE-B003`
- **Qualidade**: todas as validações de negócio passam aqui — ver [silver-checklist-odcs.md](../patterns/silver-checklist-odcs.md)

### Gold (Camada analítica)
- **Responsabilidade**: subset de colunas de negócio para BI, ad-hoc, ML e salas NL (Genie)
- **Nunca fazer**: lógica de limpeza (isso é Silver), transformações brutas
- **Formato**: Delta Lake ou tabelas otimizadas para o consumidor
- **Colunas obrigatórias**: `_updated_at`
- **Nota**: precede camada **Diamond** (multidimensional); ver [gold-analytic.md](gold-analytic.md)
- **Acesso**: somente leitura para o agente (nunca escrever via LLM)

## Regras invariantes (nunca quebrar)

1. **Raw é sagrado** — nunca modifique, nunca delete, nunca filtre
2. **Cada camada tem uma responsabilidade** — sem "atalhos" (ex: raw→gold direto)
3. **Lineage columns sempre** — toda camada tem suas colunas de rastreamento
4. **Contrato dual** — Bronze documenta schema-fonte; Silver contrato ODCS prescritivo
5. **Gates SDD/Dev Loop** — perguntas obrigatórias antes de implementar ([medallion-sdd-gates.md](../patterns/medallion-sdd-gates.md))
6. **Gold = somente leitura para o agente** — nunca `INSERT/UPDATE/DELETE` em Gold via LLM

## Exemplo de fluxo

```python
# Raw: copiar da fonte sem transformar
raw_df = spark.read.csv(source_path)
raw_df = raw_df.withColumn("_source_file", lit(source_path)) \
               .withColumn("_ingest_ts", current_timestamp())
raw_df.write.mode("append").parquet(config.raw_path())

# Bronze: preservar forma-fonte (JSON fiel) + lineage
bronze_df = spark.read.json(source_path)  # struct/array intactos
bronze_df = bronze_df \
    .withColumn("_run_id", lit(run_id)) \
    .withColumn("_batch_id", lit(batch_id)) \
    .withColumn("_ingested_at", current_timestamp()) \
    .withColumn("_source", lit(source_uri)) \
    .withColumn("_source_system", lit(source_system))  # ERP, CRM, etc.
bronze_df.write.mode("append").saveAsTable(config.bronze_table("orders"))

# Silver: normalizar + limpar + validar (contrato ODCS flat)
silver_df = bronze_df \
    .dropDuplicates(["order_id"]) \
    .filter(col("amount") > 0) \
    .withColumn("_processed_at", current_timestamp()) \
    .withColumn("_pipeline_version", lit("1.0.0")) \
    .withColumn("_source_system", col("_source_system"))
silver_df.write.mode("overwrite").saveAsTable(config.silver_table("orders"))
```
