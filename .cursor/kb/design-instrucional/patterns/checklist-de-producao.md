---
topic: checklist-de-producao
confidence: null
mcp_validated: null
---

# Padrão: Checklist de Produção

Bloco final (tipo "validação/produção" no roteiro) que consolida, num único lugar, tudo que o
leitor precisa checar antes de considerar a implementação pronta — mesmo espírito do "Definição
de Pronto" que este canônico usa para tasks de código (`rules/definicao-de-pronto.md`), aplicado
a um tutorial em vez de uma entrega de código.

## Estrutura recomendada

```markdown
# Bloco {N} — Validação e Produção

## O que verificar antes de considerar pronto

- [ ] {verificação funcional 1 — o sistema faz o que deveria}
- [ ] {verificação de segurança — credenciais não expostas, permissões mínimas}
- [ ] {verificação de custo, se aplicável — recursos que ficam ligados cobrando}
- [ ] {verificação de limpeza — recursos temporários/de teste removidos, se o guia usou
      ambiente descartável}

## Guardrails de segurança específicos deste guia

{o que este guia especificamente pede atenção — ex.: "nunca commite o token gerado no bloco 3"}

## Se algo não passou na verificação

{para cada item acima que pode falhar, um ponteiro de "volte ao bloco X" ou "veja o apêndice de
troubleshooting"}
```

## Por que isso vem no fim, não distribuído

Verificações pontuais já acontecem dentro de cada bloco de implementação ("Verificação" da
anatomia padrão). O checklist de produção é diferente: valida o **sistema como um todo**, não uma
etapa isolada — coisas que só fazem sentido checar depois que tudo está construído (ex.: "o
pipeline inteiro roda de ponta a ponta sem intervenção manual").

## Relação com o "ambiente de destino" do escopo

Se `01-escopo.md` declarou ambiente de destino como "produção", o checklist de produção deve ser
mais rigoroso (permissões, custo, rollback) do que se o ambiente é "sandbox/descartável" — não
aplique o mesmo nível de rigor de segurança a um guia que roda inteiro num ambiente que será
destruído ao final.
