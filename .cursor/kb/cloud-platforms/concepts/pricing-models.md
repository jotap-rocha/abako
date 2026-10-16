# Modelos de Precificação — Snowflake vs Databricks vs BigQuery

## Princípio comum: compute separado de storage

As três plataformas desacoplam armazenamento (barato, cresce livre) de processamento (caro,
elástico). Isso muda o approach de custo: storage nunca é o gargalo, compute é.

## Snowflake — warehouse sizing (crédito/hora)

- Unidade de compute: **virtual warehouse**, tamanhos T-shirt (XS, S, M, L, XL...), cada tamanho
  dobra os créditos/hora do anterior (XS=1 crédito/h, S=2, M=4, L=8...).
- Cobrança por **segundo** (mínimo 60s), billing separado de storage (compressed, ~$23-40/TB/mês
  conforme edição e região).
- Múltiplos warehouses podem ler os mesmos dados simultaneamente sem contenção — não há
  "cluster único" competindo por recursos entre times.
- Storage e compute escalam de forma totalmente independente; um warehouse pode ser
  redimensionado (resize) em segundos sem downtime, mas o resize é para cima/baixo, não
  auto-scaling horizontal automático dentro de uma query.

## Databricks — DBU (Databricks Unit) + cloud compute subjacente

- Cobrança em duas camadas: (1) **DBU** (Databricks Unit — taxa da plataforma, varia por tipo de
  workload: Jobs, All-Purpose, SQL Serverless, DLT) e (2) **infraestrutura cloud subjacente**
  (EC2/Azure VM/GCE que roda o cluster Spark), cobrado à parte pelo cloud provider.
- All-Purpose Compute (notebooks interativos) é mais caro por DBU que Jobs Compute (workloads
  agendados) — separar interativo de produção é uma alavanca de custo direta.
- SQL Warehouses (Serverless ou Pro) têm precificação própria, comparável a warehouse do
  Snowflake em granularidade.
- Cluster pode ter autoscaling de nós (min/max workers) — elasticidade dentro da execução de um
  job, diferente do resize manual de warehouse do Snowflake.

## BigQuery — slots (capacidade reservada) ou on-demand

- Dois modelos concorrentes: **on-demand** (paga por TB escaneado por query, ~$5-6/TB) ou
  **capacity-based** (compra de **slots** — unidades de capacidade de processamento paralelo —
  via editions Standard/Enterprise/Enterprise Plus, com compromissos de 1s, 1h, 1mo ou 1y).
- On-demand é simples de começar mas imprevisível em custo com queries mal escritas (full scan
  em tabela de TBs = fatura alta sem aviso).
- Slots dão custo previsível (capacidade fixa reservada) e favorecem cargas de alto volume e
  consistentes — o trade-off é a necessidade de estimar capacidade com antecedência.
- Storage é cobrado à parte (active vs long-term storage, o segundo com desconto automático após
  90 dias sem modificação).

## Comparação direta

| Dimensão | Snowflake | Databricks | BigQuery |
|---|---|---|---|
| Unidade de compute | Crédito/hora por warehouse | DBU + infra cloud | Slot ou $/TB escaneado |
| Granularidade de billing | Por segundo (min 60s) | Por segundo (cluster) | Por query (on-demand) ou por slot-hora |
| Previsibilidade de custo | Alta (warehouse size fixo) | Média (autoscaling varia) | Baixa on-demand / Alta com slots |
| Risco de "bill shock" | Baixo (warehouse limitado) | Médio (autoscaling sem teto) | Alto on-demand (scan não controlado) |
| Storage cobrado à parte | Sim | Sim (é o cloud storage nativo, ex: S3/ADLS) | Sim |

## Gotchas

- Databricks: esquecer de configurar `autotermination` em cluster interativo é a causa nº 1 de
  fatura surpresa — cluster fica ligado cobrando infra cloud sem uso.
- BigQuery on-demand: `SELECT *` em tabela particionada sem filtro de partição escaneia a tabela
  inteira — o otimizador não adivinha intenção, só reduz scan se a query filtra a coluna de
  partição explicitamente.
- Snowflake: warehouse maior nem sempre é mais rápido — se a query não paraleliza bem (poucos
  micro-partitions envolvidos), XL pode terminar no mesmo tempo que M gastando 2x os créditos.
