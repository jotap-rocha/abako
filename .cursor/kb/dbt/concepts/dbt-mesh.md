# dbt Mesh — Arquitetura Multi-Projeto

## O que é

dbt Mesh é o padrão arquitetural para dividir um monólito dbt em múltiplos projetos
independentes (por domínio: finance, marketing, core) que se referenciam entre si via
`ref()` com dois argumentos, em vez de um projeto único gigante.

## Componentes centrais

### Cross-project ref

Referencia um model público de outro projeto — o segundo argumento é o nome do model,
o primeiro é o nome do projeto (não o schema).

```sql
select * from {{ ref('jaffle_finance', 'fct_orders') }}
```

```sql
-- com versionamento de model
select * from {{ ref('analytics', 'fct_orders', v=1) }}
```

### dependencies.yml

Declara de qual projeto upstream o projeto atual depende — pré-requisito para o
cross-project `ref()` resolver.

```yaml
# dependencies.yml
projects:
  - name: jaffle_shop
packages:
  - package: dbt-labs/dbt_utils
    version: 1.1.1
```

### Groups — dono e fronteira de domínio

Agrupa models sob um owner responsável, formando a fronteira de domínio dentro (ou
entre) projetos.

```yaml
# models/__groups.yml
groups:
  - name: marketing
    owner: {name: Ben Jaffleck, email: ben@jaffleshop.com}
```

```yaml
# atribuir model ao grupo — "group" virou "config" a partir do dbt 1.10
models:
  - name: fct_marketing_model
    config:
      group: marketing
```

### Access — o que pode ser consumido de fora

Controla se um model pode ser referenciado fora do seu grupo/projeto.

| Access | Pode ser `ref()`'d de fora do grupo? | Uso típico |
|---|---|---|
| `private` | Não — só dentro do mesmo grupo | Staging, intermediate |
| `protected` | Sim, mas só dentro do mesmo projeto | Mart consumido por outro domínio no mesmo projeto |
| `public` | Sim, inclusive por outros projetos (Mesh) | Contrato estável entre projetos |

```yaml
models:
  - name: fct_marketing_model
    config:
      group: marketing
      access: protected
```

### Contracts — schema como API

Modelos `public` de um Mesh devem ter contrato de schema enforced — muda o tipo/nome de
coluna sem versionar quebra os projetos downstream silenciosamente sem isso.

```yaml
models:
  - name: dim_customers
    config:
      materialized: table
      contract: {enforced: true}
    columns:
      - {name: customer_id, data_type: int, constraints: [{type: not_null}]}
```

## Quando adotar Mesh vs projeto único

```
O time de dados é único e o warehouse é pequeno/médio?
    └── Projeto único — Mesh adiciona overhead de governança sem retorno

Times de domínio diferentes (finance, marketing) com deploy independente,
donos diferentes, ou > 1000 models num projeto só?
    └── Mesh — fronteiras de grupo + contracts evitam acoplamento cruzado
```

## Gotchas

- Cross-project `ref()` só resolve modelo com `access: public` — `private`/`protected`
  gera erro de compilação, não silencioso.
- `restrict-access: True` no `dbt_project.yml` bloqueia refs externas mesmo de packages —
  default é `False`, então revisar explicitamente ao adotar Mesh.
- Contracts (`contract.enforced: true`) exigem `data_type` declarado em toda coluna —
  omitir uma coluna do contrato não a esconde, quebra o build.
- `group` e `access` mudaram de chave top-level para `config:` a partir do dbt 1.10 —
  projetos legados precisam migrar a sintaxe.
