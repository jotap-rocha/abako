# Particionamento de Tópico Kafka

## O que é uma partição

Um tópico Kafka é dividido em N partições — cada partição é um log ordenado e imutável.
Partição é a unidade de paralelismo: cada partição só pode ser lida por **um** consumidor por
vez dentro de um consumer group.

```
Tópico "orders" com 4 partições:
  Partition 0: [msg0, msg1, msg2, ...]
  Partition 1: [msg0, msg1, msg2, ...]
  Partition 2: [msg0, msg1, msg2, ...]
  Partition 3: [msg0, msg1, msg2, ...]
```

## Garantia de ordenação — só dentro da partição

Kafka garante ordem **apenas dentro de uma mesma partição**. Entre partições, não há ordem
global. Se a lógica de negócio depende de ordem (ex.: eventos do mesmo `customer_id` processados
em sequência), a **mesma key sempre precisa cair na mesma partição**.

```python
# Particionamento por key: hash(key) % num_partitions decide a partição
producer.send("orders", key=customer_id.encode(), value=order_payload)
# Todo evento com o mesmo customer_id vai sempre para a mesma partição
# → ordem garantida por customer_id, não globalmente
```

## Como o Kafka decide a partição

| Estratégia | Comportamento |
|---|---|
| Com `key` definida (padrão) | `hash(key) % num_partitions` — mesma key sempre na mesma partição |
| Sem `key` (round-robin / sticky) | Distribui uniformemente entre partições, sem garantia de ordem |
| Partitioner customizado | Lógica explícita (ex.: roteamento por tenant, por região) |

## Número de partições — trade-offs

| Mais partições | Menos partições |
|---|---|
| Mais paralelismo (mais consumidores simultâneos) | Menos overhead de metadata no broker/ZooKeeper |
| Mais throughput agregado | Rebalance mais rápido |
| Mais overhead de file handles no broker | Menos paralelismo — consumidores ociosos se `consumers > partitions` |
| Rebalance mais lento com muitos consumidores | Risco de hot partition se poucas keys concentram o volume |

Regra prática: número de partições ≥ número máximo de consumidores paralelos que você vai
rodar. Partições não usadas por nenhum consumidor não geram paralelismo extra — apenas
overhead. Aumentar partições depois é possível, mas **quebra a garantia de ordem por key**
existente (novo hash space redistribui keys).

## Consumer groups e rebalanceamento

```
Consumer group "orders-processor" com 4 consumidores, tópico com 4 partições:
  Consumer 1 ← Partition 0
  Consumer 2 ← Partition 1
  Consumer 3 ← Partition 2
  Consumer 4 ← Partition 3

Se Consumer 4 cai:
  Rebalance → Partition 3 é reatribuída a outro consumidor do grupo
```

Se `num_consumers > num_partitions`, os consumidores excedentes ficam ociosos (uma partição só
tem um consumidor ativo por vez dentro do grupo).

## Hot partition (partição desbalanceada)

Quando uma key concentra desproporcionalmente o volume (ex.: um `tenant_id` gigante em sistema
multi-tenant), a partição dela vira gargalo mesmo com N partições disponíveis.

```python
# Mitigação: salting — quebra a key em sub-keys artificiais para distribuir
def salted_key(customer_id: str, num_shards: int = 4) -> str:
    shard = hash(customer_id) % num_shards
    return f"{customer_id}#{shard}"
# Cuidado: perde ordenação total por customer_id — só use se a lógica tolerar
```

## Gotchas

- **Aumentar partições de um tópico existente redistribui o hash space** — eventos com a mesma
  key podem começar a cair em partições diferentes, quebrando ordenação assumida por
  consumidores existentes. Planeje o número de partições no design, não depois.
- **Sem key definida, não há garantia de ordem nenhuma** — se a lógica de negócio não depende de
  ordem, tudo bem; se depende (ex.: CDC, ver `../patterns/cdc-debezium.md`), sempre definir key.
- **Muitos tópicos com muitas partições sobrecarregam o broker** (metadata, file handles) — não
  superdimensione partições "por precaução".
- **CDC do Debezium particiona por chave primária da tabela por padrão** — garante que updates
  da mesma linha chegam em ordem ao consumidor, mas não garante ordem entre tabelas diferentes.

## Referências
- `delivery-semantics.md` — como partição interage com garantias de entrega
- `../patterns/cdc-debezium.md` — particionamento por chave primária em CDC
- `.claude/kb/multi-tenant/concepts/isolation-models.md` — isolamento multi-tenant (paralelo ao hot partition por tenant)
