# Pools e Prioridade para Controle de Concorrência

## O problema

Múltiplas DAGs/tasks competem pelo mesmo recurso limitado (conexões de um DB legado, rate
limit de uma API externa, slots de uma warehouse). Sem controle, o Airflow dispara todas as
tasks elegíveis ao mesmo tempo — o recurso externo satura ou aplica throttling/erro.

## Criando um pool

```bash
airflow pools set db_legado_pool 5 "Máximo 5 conexões simultâneas ao DB legado"
```

Ou versionado como código (IaC), aplicado num passo de deploy:

```python
# config/pools.py — executado uma vez no setup/deploy do ambiente
from airflow.models import Pool
from airflow.utils.session import create_session

def sync_pools():
    pools = {
        "db_legado_pool": (5, "Máximo 5 conexões simultâneas ao DB legado"),
        "partner_api_pool": (2, "Rate limit do parceiro: 2 req/s efetivo"),
    }
    with create_session() as session:
        for name, (slots, description) in pools.items():
            if not session.query(Pool).filter(Pool.pool == name).first():
                session.add(Pool(pool=name, slots=slots, description=description))
```

## Atribuindo uma task a um pool

```python
@task(pool="db_legado_pool", pool_slots=1)
def sync_legacy_table(table: str) -> None:
    ...
```

`pool_slots` (default 1) permite que uma task específica "pese mais" — ex.: uma task que
sabidamente usa 3 conexões simultâneas internamente declara `pool_slots=3`.

## `priority_weight` — ordem de execução quando o pool está cheio

```python
@task(pool="db_legado_pool", priority_weight=10)  # maior peso = prioridade maior
def sync_critical_table() -> None:
    ...

@task(pool="db_legado_pool", priority_weight=1)   # peso baixo = fila normal
def sync_nice_to_have_table() -> None:
    ...
```

Quando o pool está no limite de slots, o scheduler escolhe a próxima task a liberar por
`priority_weight` (maior primeiro), não por ordem de chegada.

## `weight_rule` — como o peso se propaga em pipelines com dependências

```python
@task(priority_weight=5, weight_rule="downstream")
def critical_extract() -> None:
    ...
```

| `weight_rule` | Efeito |
|---|---|
| `downstream` (padrão) | Peso da task = próprio peso + soma dos pesos de todas as tasks downstream — tasks no início de uma cadeia longa e crítica sobem de prioridade automaticamente |
| `upstream` | Peso = próprio peso + soma dos pesos upstream |
| `absolute` | Usa exatamente o `priority_weight` declarado, sem propagação |

## Combinando pool + dynamic task mapping

```python
process_file.override(pool="partner_api_pool", max_active_tis_per_dag=2).expand(
    path=list_files()
)
```

Mapear 500 arquivos não significa 500 chamadas simultâneas à API do parceiro — o pool garante
que, entre **todas** as DAGs/tasks que competem pelo mesmo recurso, o teto real de concorrência
é respeitado.

## Checklist

- [ ] Todo recurso externo com limite de concorrência conhecido tem um pool dedicado
- [ ] `pool_slots` reflete o custo real da task no recurso (não assumir sempre 1)
- [ ] Tasks de negócio crítico têm `priority_weight` maior que tasks best-effort no mesmo pool
- [ ] Pools são criados via IaC/script de deploy — não só manualmente pela UI (perde-se em reset de ambiente)
