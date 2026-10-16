---
topic: publico-alvo-e-pre-requisitos
confidence: null
mcp_validated: null
---

# Público-Alvo e Pré-Requisitos

Todo o resto do roteiro depende de responder bem "quem é o leitor" primeiro. É a primeira coisa
que `guia-escopo` estrutura, antes até do glossário.

## As perguntas que definem o público

- **Nível técnico geral**: iniciante no assunto, ou experiente em área adjacente e novo só nesta
  ferramenta/tecnologia específica?
- **O que o leitor já tem**: ambiente instalado, contas/credenciais, conhecimento de conceitos
  vizinhos que este guia não vai reexplicar?
- **O que o leitor NÃO tem**: se o guia assume algo que a maioria do público real não tem, isso
  vira pré-requisito explícito ou um bloco de preparação adicional — nunca uma suposição
  silenciosa.

## Pré-requisitos vs não-objetivos

São coisas diferentes e ambas precisam estar declaradas:
- **Pré-requisito**: o que o leitor precisa ter *antes* de começar (ex.: "conta ativa no
  provedor X", "Python 3.11+ instalado").
- **Não-objetivo**: o que o guia explicitamente *não* ensina, mesmo sendo do mesmo domínio (ex.:
  um guia de deploy não ensina a escrever a aplicação do zero).

Confundir os dois é o erro mais comum: um guia que lista "saber Python" como não-objetivo em vez
de pré-requisito engana o leitor sobre o que precisa saber antes de começar.

## Como calibrar sem inflar nem reduzir escopo

- Se metade dos blocos de preparação existe só para compensar um pré-requisito que poderia
  simplesmente ser exigido antes ("tenha Docker instalado"), declare como pré-requisito em vez
  de bloco.
- Se um pré-requisito é raro de já ter (ex.: uma conta paga específica), o guia deveria ou
  incluir o passo de obtê-lo como bloco de preparação, ou avisar isso logo na introdução — nunca
  deixar o leitor descobrir no meio do bloco 5.

## Tempo estimado como sinal de calibração

O campo "tempo estimado" (perguntado em `guia-escopo`) não é só informativo — é um sinal de
alerta. Se o tempo estimado passa de ~2h para um guia de "implementação técnica" simples, é sinal
de que o escopo pode estar largo demais para um único guia (considere dividir em dois).
