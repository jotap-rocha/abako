# Slowly Changing Dimensions (SCD) — Tipos 0 a 6

## O problema

Dimensões mudam ao longo do tempo (ex.: cliente muda de endereço, produto muda de categoria).
SCD define **como o modelo trata essa mudança**: ignora, sobrescreve, versiona, ou combina
estratégias.

## Os tipos

### Type 0 — Retain Original

Atributo nunca muda depois de inserido. Usado para fatos verdadeiramente imutáveis
(ex.: data de nascimento, número de série original de um produto).

### Type 1 — Overwrite

Sobrescreve o valor antigo. **Não há histórico.** Simples, mas perde a linha do tempo.

```sql
UPDATE dim_customer SET city = 'São Paulo' WHERE customer_id = 42;
-- valor anterior de "city" é perdido para sempre
```

Use quando o histórico do atributo não importa para análise (ex.: corrigir erro de digitação).

### Type 2 — Add New Row (o mais usado)

Cria uma **nova linha** a cada mudança, com controle de vigência (`effective_date`,
`end_date`, `is_current`). Preserva histórico completo. Ver `patterns/scd-type-2.md` para
implementação completa.

```
customer_sk | customer_id | city         | effective_date | end_date   | is_current
1           | 42          | Rio de Janeiro| 2024-01-01     | 2025-03-15 | false
2           | 42          | São Paulo     | 2025-03-15     | NULL       | true
```

### Type 3 — Add New Column

Adiciona uma coluna para guardar o valor **anterior** (geralmente só o penúltimo estado, não
todo o histórico).

```sql
ALTER TABLE dim_customer ADD COLUMN previous_city STRING;
-- guarda só 1 versão anterior, não a série histórica completa
```

Uso raro — só quando o negócio precisa comparar "antes vs depois" mas não a série completa.

### Type 4 — History Table

Mantém a dimensão principal só com o valor **atual** (Type 1) e move o histórico para uma
tabela separada (`dim_customer_history`). Separa consultas de "estado atual" (rápidas) de
consultas de "histórico" (menos frequentes, tabela maior).

### Type 5 — Type 1 + Mini-dimension

Combina Type 1 na dimensão principal com uma "mini-dimensão" separada para atributos que mudam
muito (ex.: faixa etária, faixa de renda) referenciada por chave na fact table. Evita que a
dimensão principal cresça demais com histórico de atributos voláteis.

### Type 6 — Type 1 + 2 + 3 (Hybrid)

Combina as três abordagens: mantém histórico completo (Type 2, várias linhas), guarda o valor
atual replicado em toda linha histórica (Type 1, coluna `current_city`) e o valor anterior
(Type 3, coluna `previous_city`). Permite consultar "como era na época do fato" e "como é hoje"
na mesma query sem join adicional.

## Tabela de decisão

| Tipo | Preserva histórico? | Complexidade | Quando usar |
|---|---|---|---|
| 0 | N/A (imutável) | Trivial | Atributo nunca muda por definição |
| 1 | Não | Baixa | Correção de erro, atributo sem valor analítico histórico |
| 2 | Sim (completo) | Média | Caso padrão — quase sempre a escolha certa |
| 3 | Parcial (1 versão) | Baixa | Comparação "antes vs depois" pontual |
| 4 | Sim (tabela separada) | Média-alta | Volume alto de mudanças, separar quente/frio |
| 5 | Sim (via mini-dim) | Alta | Atributo muda com muita frequência (ex.: score) |
| 6 | Sim (híbrido) | Alta | Precisa histórico completo + estado atual na mesma linha |

## Gotchas

- Type 2 é o default correto na maioria dos casos — só desvie para outros tipos com uma razão
  concreta (volume, frequência de mudança, requisito específico de query).
- Nunca aplique Type 2 em TODOS os atributos de uma dimensão por padrão — atributos que mudam
  com muita frequência (ex.: "última vez que fez login") geram explosão de linhas. Separe em
  mini-dimensão (Type 5) ou não versione.
- `is_current` como boolean é conveniente para queries, mas `end_date IS NULL` é a fonte de
  verdade — mantenha os dois sincronizados ou derive `is_current` sempre por view.
