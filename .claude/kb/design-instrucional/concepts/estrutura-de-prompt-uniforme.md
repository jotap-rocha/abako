---
topic: estrutura-de-prompt-uniforme
confidence: null
mcp_validated: null
---

# Estrutura de Prompt Uniforme

"Prompt" aqui é usado no sentido de "instrução de bloco" — não prompt de LLM. Todo bloco de
implementação de um guia segue a mesma anatomia de 5 partes (ver
`patterns/bloco-contexto-conceito-codigo-validacao.md` para o template completo). Este conceito
explica *por que* a uniformidade importa.

## O que a uniformidade economiza

Quando todo bloco segue a mesma estrutura, o leitor para de gastar atenção em "onde está a parte
que importa" e passa a gastar atenção só no conteúdo novo. Isso é redução de carga cognitiva
extrínseca (o esforço de navegar o material) para deixar mais orçamento de atenção para a carga
intrínseca (entender o conceito novo em si).

## As 5 partes e o que cada uma resolve

1. **Contexto** — resolve "por que estou fazendo isso agora e não antes/depois".
2. **Conceito** — resolve "o que isso significa", antes de "como fazer isso".
3. **Implementação** — o comando/código em si, com comentário do que cada parte faz.
4. **Verificação** — resolve "como sei que funcionou", com sinal concreto.
5. **Critério de aceite** — resolve "posso seguir em frente com confiança", em formato checável.

## Quando quebrar a uniformidade (e quando não)

Blocos de contextualização e apêndices podem omitir "Implementação"/"Verificação" — mas a decisão
deve ser explícita (`N/A — {motivo}`), nunca a seção simplesmente desaparecendo sem explicação.
Isso evita que o leitor se pergunte se esqueceram de escrever aquela parte.

Nunca quebre a ordem interna (Conceito sempre antes de Implementação) mesmo em blocos curtos —
é a regra mais importante deste domínio inteiro.

## Relação com o padrão de teste-antes-de-implementar

O harness deste canônico já aplica uma ideia irmã em `harness-build.md`: escrever o teste antes
da implementação, para provar que o teste testa algo real. Aqui a ideia equivalente é escrever a
explicação conceitual antes do comando — o comando sem conceito é "código sem teste": funciona,
mas ninguém sabe por quê nem quando vai quebrar.
