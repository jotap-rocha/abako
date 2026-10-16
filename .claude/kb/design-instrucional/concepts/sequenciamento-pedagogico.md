---
topic: sequenciamento-pedagogico
confidence: null
mcp_validated: null
---

# Sequenciamento Pedagógico

A ordem dos blocos de um guia é a decisão mais importante do roteiro — mais do que o conteúdo de
cada bloco individual. Um guia tecnicamente correto mas mal sequenciado ainda frustra o leitor.

## A progressão padrão

```
1. Contextualização — o que vai ser construído e por quê. Glossário dos termos que aparecem
   daqui pra frente. O leitor sai daqui sabendo "para onde estou indo".
2. Preparação técnica — instalação, autenticação, conceitos de plataforma necessários antes de
   qualquer implementação. Termina antes do primeiro bloco de implementação, nunca intercalada.
3. Implementação — a maior parte do guia. Cada bloco entrega um resultado observável e
   incremental sobre o anterior.
4. Validação/produção — checklist de verificação do todo, guardrails de segurança, o que checar
   antes de considerar "pronto".
5. Apêndices — referência que não precisa ser lida em sequência (comandos compilados,
   troubleshooting, FAQ).
```

## Por que essa ordem e não outra

- **Contextualização antes de preparação**: sem saber o que vai ser construído, instalar
  ferramentas parece trabalho arbitrário — o leitor perde motivação.
- **Preparação nunca intercalada com implementação**: alternar "instale X" / "implemente Y" /
  "instale Z" força o leitor a trocar de modo mental repetidamente. Agrupar preparação reduz
  fricção.
- **Implementação em blocos incrementais**: cada bloco assume só o que os blocos anteriores já
  entregaram — nunca um bloco que depende de algo ainda não construído.
- **Validação no fim, não distribuída**: pequenas verificações acontecem dentro de cada bloco de
  implementação; a validação final é sobre o sistema como um todo, não sobre uma etapa isolada.

## Como decidir a granularidade dos blocos de implementação

Regra prática: **1 bloco = 1 resultado observável**. Se um bloco entrega dois resultados
não relacionados, é candidato a virar dois blocos. Se dois blocos são pequenos demais e sempre
executados juntos, considere fundir — a fragmentação excessiva também cansa.

## Gotchas

- Preparação técnica que "poderia ser feita depois" (ex.: configurar um dashboard opcional) não
  pertence ao bloco de preparação principal — vira bloco de implementação tardio ou apêndice.
- Guias de migração (tipo "c" em `guia-brainstorm`) têm uma variação: a progressão é
  "estado atual → passo de corte → estado novo → rollback se necessário", não a progressão padrão
  acima.
