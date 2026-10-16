# Template uniforme de etapa (bloco)

Todo bloco de implementação de um guia segue esta anatomia. Blocos de contextualização e
apêndice podem omitir "Implementação"/"Verificação" quando não se aplicam — mas devem declarar
`N/A — {motivo}` em vez de remover a seção silenciosamente.

## Template vazio

```markdown
# Bloco {N} — {Título}

## Contexto
{Por que este bloco existe agora. O que o leitor já tem antes dele. O que muda depois.}

## Conceito
{O "porquê" antes do "como". Glossário aplicado. Tabela comparativa se ajudar a decidir entre
opções. Diagrama em texto (ASCII) se a relação entre partes não for óbvia em prosa.}

## Implementação
{Comando(s)/código com comentário do que cada parte faz. Alternativas conforme contexto do
leitor, se houver mais de um caminho válido. Armadilhas conhecidas marcadas explicitamente.}

## Verificação
{O que olhar/rodar agora para confirmar que funcionou. Número esperado, print de tela, ou
comando de teste — nunca "deve funcionar" sem um sinal concreto.}

## Critério de aceite
- [ ] {critério testável 1}
- [ ] {critério testável 2}
```

## Exemplo preenchido (adaptado do padrão de referência do fluxo)

```markdown
# Bloco 3 — Autenticação com a CLI

## Contexto
No bloco anterior você instalou a CLI. Antes de rodar qualquer comando que toque o workspace
remoto, a CLI precisa de credenciais válidas — sem isso, os próximos blocos falham com erro de
permissão confuso.

## Conceito
A CLI suporta dois modos de autenticação: token pessoal (rápido, expira) e OAuth de máquina
(mais lento de configurar, não expira em uso normal). Para este guia, usamos token pessoal —
é o caminho mais curto para um ambiente de aprendizado, não o recomendado para produção
compartilhada.

## Implementação
```bash
cli auth login --token $MEU_TOKEN
```
**Pegadinha comum:** se a variável de ambiente não estiver exportada na sessão atual (só
definida em outro terminal), o comando falha silenciosamente com "token inválido" — confirme
com `echo $MEU_TOKEN` antes.

## Verificação
```bash
cli auth whoami
```
Deve retornar seu usuário e o workspace ativo. Se retornar vazio, a autenticação não colou.

## Critério de aceite
- [ ] `cli auth whoami` retorna usuário + workspace
- [ ] Nenhum erro de permissão ao listar recursos (`cli list`)
```
