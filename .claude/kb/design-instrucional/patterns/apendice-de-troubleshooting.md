---
topic: apendice-de-troubleshooting
confidence: null
mcp_validated: null
---

# Padrão: Apêndice de Troubleshooting

Consolida, num único lugar navegável, todas as "pegadinhas comuns" que apareceram declaradas
dentro dos blocos de implementação — sem duplicar o conteúdo, apenas indexando.

## Quando criar este apêndice

Regra prática (ver `quick-reference.md` da KB): se o roteiro já acumulou 3+ pegadinhas
declaradas em blocos diferentes, vale consolidar num apêndice. Guias curtos (poucos blocos, 1-2
pegadinhas) não precisam — a pegadinha já está visível dentro do bloco relevante.

## Estrutura recomendada

```markdown
# Apêndice {letra} — Troubleshooting

## Erros comuns

### "{mensagem de erro ou sintoma}"
**Causa:** {por que isso acontece}
**Solução:** {o que fazer}
**Onde isso costuma aparecer:** {bloco N, se relevante}

### "{outro sintoma}"
...

## Perguntas frequentes

### {pergunta}
{resposta direta, sem rodeio}
```

## Regra de não-duplicação

Se uma pegadinha já está marcada dentro de um bloco ("Pegadinha comum: ..."), o apêndice não
repete o texto inteiro — referencia o bloco (`ver Bloco N`) e adiciona só o que o bloco não
cobriu (ex.: uma segunda causa possível para o mesmo sintoma, ou uma solução alternativa).

## Fonte dos itens do apêndice

Ao escrever este bloco, `guia-etapas` deve reler todos os blocos de implementação já escritos e
extrair as pegadinhas marcadas — não inventar problemas hipotéticos que não foram observados nos
blocos anteriores nem mencionados no material-fonte.
