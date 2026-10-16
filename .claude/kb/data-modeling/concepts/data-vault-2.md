# Data Vault 2.0 — Hubs, Links, Satellites

## O que é

Metodologia de modelagem para a camada de integração de um data warehouse, criada por Dan
Linstedt. Otimizada para **auditabilidade, rastreabilidade histórica e agilidade de mudança de
schema** — não para consumo direto por BI (isso fica na camada de apresentação, geralmente um
star schema derivado do Vault).

## As 3 entidades core

### Hub — identidade de negócio

Armazena **apenas a chave de negócio (business key)** e metadados de carga. Nunca muda depois de
inserido (append-only, imutável).

```sql
CREATE TABLE hub_customer (
    customer_hk     BINARY(32) PRIMARY KEY,  -- hash da business key
    customer_bk     STRING NOT NULL,          -- business key (ex.: CPF, customer_id do ERP)
    load_dts        TIMESTAMP NOT NULL,       -- quando foi carregado
    record_source    STRING NOT NULL          -- de qual sistema veio
);
```

### Link — relacionamento entre hubs

Representa uma **transação ou associação** entre duas ou mais business keys. Também
append-only e imutável.

```sql
CREATE TABLE link_customer_order (
    link_hk         BINARY(32) PRIMARY KEY,   -- hash de (customer_hk + order_hk)
    customer_hk     BINARY(32) NOT NULL REFERENCES hub_customer,
    order_hk        BINARY(32) NOT NULL REFERENCES hub_order,
    load_dts        TIMESTAMP NOT NULL,
    record_source    STRING NOT NULL
);
```

### Satellite — contexto descritivo e histórico

Armazena os **atributos que mudam ao longo do tempo**, associados a um Hub ou Link. É aqui que
mora o histórico — cada mudança gera uma nova linha, nunca um UPDATE.

```sql
CREATE TABLE sat_customer_details (
    customer_hk     BINARY(32) NOT NULL REFERENCES hub_customer,
    load_dts        TIMESTAMP NOT NULL,       -- início de validade da versão
    load_end_dts    TIMESTAMP,                -- fim de validade (NULL = versão atual)
    hash_diff       BINARY(32) NOT NULL,      -- hash dos atributos, detecta mudança
    email           STRING,
    phone           STRING,
    record_source    STRING NOT NULL,
    PRIMARY KEY (customer_hk, load_dts)
);
```

## Por que essa separação

- **Hubs isolam a chave de negócio** — se o sistema fonte muda de ERP, só o hub daquela entidade
  é afetado, não o modelo inteiro.
- **Links isolam relacionamentos** — novos tipos de relação viram novos links, sem alterar
  tabelas existentes (schema é aditivo, nunca destrutivo).
- **Satellites isolam a velocidade de mudança** — atributos que mudam rápido (ex.: endereço)
  podem ficar em um satellite separado de atributos estáveis (ex.: data de nascimento), evitando
  reescrever histórico de coisas que não mudaram.
- **Tudo é append-only** — nada é feito UPDATE/DELETE na camada raw do Vault. Isso dá
  auditabilidade total: é possível reconstruir o estado do dado em qualquer ponto no tempo.

## Quando usar Data Vault 2.0

| Cenário | Recomendação |
|---|---|
| Múltiplas fontes de dados heterogêneas e mutantes (fusões, trocas de ERP) | Forte encaixe |
| Exigência regulatória de auditoria/rastreabilidade total (banking, saúde) | Forte encaixe |
| Time pequeno, um único sistema fonte estável, consumo direto por BI | Star schema é mais simples |
| Camada de apresentação para analistas de negócio | Não usar Vault direto — derive um star schema |

## Gotchas

- Data Vault não substitui a camada de apresentação (Gold/dimensional) — é a camada de
  integração (equivalente a Silver). Sempre existe uma camada dimensional derivada por cima.
- `hash_diff` no satellite é essencial para não gerar linha nova quando nada mudou — sem ele,
  toda carga cria um registro duplicado mesmo sem mudança real.
- Business key (`_bk`) precisa ser estável e única por definição de negócio — escolher a chave
  errada (ex.: um ID técnico que muda entre sistemas) quebra a premissa central do modelo.
