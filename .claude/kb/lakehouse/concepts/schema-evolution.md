---
topic: schema-evolution
confidence: null
mcp_validated: null
---

# Evolução de Schema em Tabelas Versionadas

## Por que é diferente de Hive tradicional

Em tabelas Hive clássicas, colunas são resolvidas por **posição** no schema. Renomear ou
reordenar uma coluna quebra a leitura de arquivos antigos escritos com a ordem anterior — na
prática, schema evolution segura em Hive puro se resume a "adicionar coluna no fim".

Formatos abertos (Iceberg, Delta com column mapping) resolvem colunas por **ID estável**, não por
posição. Isso desacopla o schema lógico do layout físico dos arquivos Parquet, permitindo
operações que antes exigiam reescrever a tabela inteira.

## O que vira operação só-de-metadados (sem reescrever dados)

| Operação | Iceberg (field IDs) | Delta Lake (column mapping) |
|---|---|---|
| Adicionar coluna (nullable) | Sim | Sim |
| Remover coluna | Sim | Sim (com `column mapping mode` habilitado) |
| Renomear coluna | Sim | Sim (com column mapping) |
| Reordenar colunas | Sim | Sim (com column mapping) |
| Ampliar tipo (`int`→`long`, `float`→`double`) | Sim (widening) | Sim (`mergeSchema` + tipos compatíveis) |
| Estreitar tipo (`long`→`int`) | Não — requer nova coluna + backfill | Não — requer nova coluna + backfill |
| Mudar tipo incompatível (`string`→`int`) | Não | Não |

Sem column mapping habilitado, Delta Lake volta a resolver por nome/posição do schema Parquet
subjacente e perde parte dessa flexibilidade — é uma feature que precisa ser ligada
explicitamente na tabela, não é o padrão em todas as versões.

## Estratégias em pipelines (Medallion)

Ver também `.claude/kb/pipeline/concepts/schema-evolution.md` para a decision tree geral de
merge/quarantine/fail — este arquivo cobre o mecanismo do table format; aquele cobre a política
de pipeline.

- **Aditiva e não-destrutiva** (nova coluna nullable) → aplicar merge automático é seguro.
- **Destrutiva** (coluna removida, tipo estreitado) → nunca aplicar automático; quarantine +
  revisão humana, porque consumidores downstream podem depender do campo.
- **Ampliação de tipo** → geralmente segura para aplicar automático (não perde dados), mas ainda
  assim vale logar a mudança para auditoria de contrato.

## Gotchas

- **Schema evolution não é retroativo**: mudar o schema não reescreve arquivos Parquet já
  gravados — leituras antigas continuam válidas porque o motor reconcilia via field ID/mapping no
  momento da leitura, não porque os bytes mudaram.
- **Nested types (structs, arrays, maps) são mais restritivos**: evolução dentro de campos
  aninhados tem menos suporte que colunas top-level — testar antes de assumir paridade.
- **Column mapping do Delta tem custo de leitura**: uma vez habilitado, não pode ser desabilitado
  sem reescrever a tabela — decisão de mão única.
- **Consumidores externos ao catálogo** (ex.: leitura direta de Parquet fora do table format)
  não veem a resolução por ID/mapping e podem quebrar silenciosamente após rename.
