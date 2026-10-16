# Checklist didático — regras de sequenciamento

Aplique este checklist ao revisar um roteiro (`02-roteiro.md`) ou um bloco individual
(`03-etapas/*.md`).

## Sequenciamento entre blocos

- [ ] Nenhum bloco de implementação vem antes do glossário que define os termos que ele usa.
- [ ] Nenhum bloco depende de uma ferramenta/credencial que só é instalada/criada num bloco
      posterior.
- [ ] A ordem reflete dependência real, não a ordem "mais fácil de escrever" — se um bloco não
      tem por que vir antes de outro, prefira a ordem que reduz o número de conceitos novos
      apresentados de uma vez.
- [ ] Blocos de preparação (instalação, autenticação, conceitos de plataforma) terminam antes do
      primeiro bloco de implementação — nunca intercalados.

## Dentro de um bloco

- [ ] "Conceito" aparece antes de "Implementação" — nunca um comando sem explicação do que ele
      faz e por que agora.
- [ ] O bloco entrega **um** resultado observável, não vários — se um bloco tenta ensinar duas
      coisas não relacionadas, é candidato a virar dois blocos.
- [ ] "Verificação" dá um sinal concreto (número, print, saída de comando) — nunca "deve
      funcionar".
- [ ] Armadilhas conhecidas do domínio estão declaradas explicitamente, não deixadas para o
      leitor descobrir sozinho.
- [ ] Critério de aceite é testável — se não dá para marcar certo/errado objetivamente, reescreva.

## Sinais de que um bloco está tentando ensinar coisa demais

- Mais de ~3 comandos novos sem nenhuma verificação intermediária.
- A seção "Conceito" precisa de mais de um parágrafo por termo novo introduzido.
- O bloco introduz um conceito e o usa imediatamente sem nenhuma explicação de por quê essa
  abordagem foi escolhida em vez de outra.

Quando detectar isso: quebre o bloco em dois, com um ponto de verificação entre eles.

## Sinais de que o guia como um todo está desbalanceado

- Blocos de preparação somam mais da metade do guia — considere se parte pode virar apêndice
  ("configuração alternativa") em vez de bloco principal.
- Nenhum apêndice de troubleshooting existe, mas o roteiro já tem 3+ "pegadinhas comuns"
  espalhadas pelos blocos — consolide num apêndice de referência rápida.
- O glossário tem menos de 3 termos para um guia com 10+ blocos técnicos — provavelmente termos
  estão sendo introduzidos inline sem passar pelo glossário centralizado.
