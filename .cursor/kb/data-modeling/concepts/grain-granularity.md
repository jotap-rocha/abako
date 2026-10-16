# Grão de Fato e Granularidade

## O que é grão

**Grão** (grain) é a definição precisa do que **uma linha** da fact table representa. É a
primeira decisão de qualquer modelagem dimensional (metodologia Kimball) — antes de escolher
dimensões ou medidas.

> "Declare o grão" é o primeiro passo do processo Kimball de 4 etapas: (1) escolher o processo
> de negócio, (2) declarar o grão, (3) identificar dimensões, (4) identificar fatos/medidas.

## Como declarar um grão

O grão deve ser uma frase única e inequívoca, não uma lista de colunas.

```
Errado:  "vendas por produto, loja e data"        (ambíguo — 1 linha = 1 dia agregado? 1 item?)
Correto: "uma linha por item de linha de venda"    (1 linha = 1 produto dentro de 1 transação)
```

Toda dimensão e métrica na fact table deve ser **consistente com esse grão** — se o grão é
"1 linha por item de venda", não pode haver uma coluna `total_da_venda` (isso pertence a um
grão mais alto, "1 linha por transação").

## Granularidade fina vs grossa

| | Grão fino (atômico) | Grão grosso (agregado) |
|---|---|---|
| Exemplo | 1 linha por item de venda | 1 linha por dia por loja |
| Flexibilidade analítica | Máxima — qualquer agregação é possível depois | Limitada — só responde perguntas no nível já agregado |
| Volume de dados | Alto | Baixo |
| Quando usar | Sempre que possível na camada de fato principal | Fact tables de resumo (summary/aggregate) derivadas |

**Regra Kimball:** sempre modele no grão **mais atômico disponível** na fonte. Agregações são
fáceis de derivar de dados atômicos (basta um `GROUP BY`); o inverso é impossível — uma vez
agregado, o detalhe se perde para sempre.

## Grão e os 3 tipos de fact table

- **Transaction fact table**: grão = 1 evento discreto (1 linha por venda, 1 linha por clique).
  Mais atômico possível.
- **Periodic snapshot**: grão = 1 linha por entidade por período (ex.: 1 linha por conta por
  mês — saldo no fechamento do mês).
- **Accumulating snapshot**: grão = 1 linha por instância de processo, atualizada conforme o
  processo avança por seus estágios (ex.: 1 linha por pedido, colunas de data para cada etapa
  do fulfillment). Ver `patterns/accumulating-snapshot.md`.

## Erros comuns de grão

1. **Grão misto na mesma tabela**: misturar linhas de detalhe com linhas de subtotal na mesma
   fact table (ex.: uma linha por item + uma linha extra por "total do pedido"). Sempre quebra
   `SUM()` por duplicar valores. Nunca misture grãos — se precisa dos dois níveis, são duas
   fact tables.
2. **Grão implícito não documentado**: time de dados assume um grão, mas não o declara em lugar
   nenhum. Six meses depois, alguém adiciona uma coluna que só faz sentido em outro grão, e a
   tabela vira uma mistura inconsistente.
3. **Fan-out em joins**: fazer JOIN de uma fact table fina com uma dimensão que tem
   multiplicidade (ex.: join de fact de vendas com uma dimensão de "promoções aplicadas" que
   tem N promoções por venda) sem perceber que isso duplica linhas da fact table.

## Gotcha central

Se você não consegue completar a frase "uma linha nesta tabela representa exatamente ___", a
tabela ainda não tem grão definido — pare e defina antes de desenhar colunas.
