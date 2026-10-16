# Bridge Table — Relações Many-to-Many

## O problema

Star schema assume que cada linha de fato se relaciona com **exatamente uma** linha de cada
dimensão (multiplicidade 1:N entre dimensão e fato). Quando a relação real é N:N — ex.: um
paciente tem múltiplos diagnósticos, um empréstimo tem múltiplos garantidores, uma venda tem
múltiplas promoções aplicadas — juntar direto explode (fan-out) e duplica medidas.

```
-- Errado: join direto de fact com uma dimensão multivalorada
SELECT SUM(f.amount)
FROM fact_loan f
JOIN dim_guarantor g ON f.loan_id = g.loan_id  -- 1 empréstimo, 3 garantidores
-- resultado: amount contado 3x
```

## A solução: bridge table

Tabela intermediária que resolve a relação N:N sem forçar a fact table a ter grão errado.

```sql
CREATE TABLE bridge_loan_guarantor (
    loan_sk          BIGINT NOT NULL REFERENCES fact_loan,
    guarantor_sk      BIGINT NOT NULL REFERENCES dim_guarantor,
    weighting_factor  DECIMAL(5,4) NOT NULL,  -- soma = 1.0 por loan_sk
    PRIMARY KEY (loan_sk, guarantor_sk)
);
```

## Duas estratégias de uso

### 1. Weighting factor — quando a medida precisa permanecer aditiva

Cada linha da bridge carrega um peso (soma 1.0 por chave de fato). Multiplica a medida pelo
peso antes de agregar — evita duplicação e mantém `SUM()` correto.

```sql
-- 1 empréstimo de R$300k com 3 garantidores igualmente responsáveis
INSERT INTO bridge_loan_guarantor VALUES
    (loan_sk_1, guarantor_sk_A, 0.3333),
    (loan_sk_1, guarantor_sk_B, 0.3333),
    (loan_sk_1, guarantor_sk_C, 0.3334);

SELECT g.guarantor_name, SUM(f.amount * b.weighting_factor) AS attributed_amount
FROM fact_loan f
JOIN bridge_loan_guarantor b ON f.loan_sk = b.loan_sk
JOIN dim_guarantor g          ON b.guarantor_sk = g.guarantor_sk
GROUP BY g.guarantor_name;
-- SUM total across guarantors = amount original, sem duplicar
```

### 2. Sem weighting factor — quando só precisa listar/filtrar, não somar

Se a query é "quais pacientes têm diagnóstico X" (filtro/listagem, não soma de medida), a
bridge sem peso é suficiente — a duplicação de linhas em `JOIN` não distorce a resposta.

```sql
CREATE TABLE bridge_patient_diagnosis (
    encounter_sk    BIGINT NOT NULL REFERENCES fact_encounter,
    diagnosis_sk    BIGINT NOT NULL REFERENCES dim_diagnosis
    -- sem weighting_factor: usado só para filtro/exists, nunca para SUM de medida
);

-- Correto para filtro (não soma nada):
SELECT DISTINCT e.encounter_id
FROM fact_encounter e
JOIN bridge_patient_diagnosis b ON e.encounter_sk = b.encounter_sk
JOIN dim_diagnosis d             ON b.diagnosis_sk = d.diagnosis_sk
WHERE d.diagnosis_code = 'E11.9';
```

## Bridge table para hierarquias variáveis (dimensão recursiva)

Outra aplicação comum: representar hierarquia organizacional de profundidade variável (ex.:
estrutura de reporte de funcionários) sem recursão em query.

```sql
CREATE TABLE bridge_org_hierarchy (
    ancestor_sk      BIGINT NOT NULL REFERENCES dim_employee,
    descendant_sk    BIGINT NOT NULL REFERENCES dim_employee,
    depth            INT NOT NULL   -- 0 = self, 1 = filho direto, 2 = neto...
);

-- "todos que reportam, direta ou indiretamente, ao gerente X"
SELECT e.employee_name
FROM bridge_org_hierarchy b
JOIN dim_employee e ON b.descendant_sk = e.employee_sk
WHERE b.ancestor_sk = :manager_sk AND b.depth > 0;
```

## Checklist

- [ ] Identificou que a relação é genuinamente N:N (não apenas uma FK mal desenhada 1:N)
- [ ] Decidiu se a medida final precisa ser aditiva → usa `weighting_factor`
- [ ] Se `weighting_factor`, validou que a soma por chave de fato é 1.0 (constraint de
      qualidade, testável em pipeline)
- [ ] Documentou no grão da fact table que a bridge existe — quem faz `JOIN` direto sem saber
      da bridge vai duplicar dado sem perceber

## Gotchas

- O erro mais comum é esquecer a bridge e fazer `JOIN` direto da fact com a dimensão
  multivalorada "porque funcionou no teste" — funciona quando todo registro de teste tem
  cardinalidade 1, quebra em produção quando aparece o primeiro caso com cardinalidade N.
- Bridge sem `weighting_factor` usada para `SUM()` de medida é o segundo erro mais comum —
  sempre pergunte "esta query agrega uma medida numérica?" antes de decidir se precisa de peso.
