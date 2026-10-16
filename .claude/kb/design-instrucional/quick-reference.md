---
domain: design-instrucional
topic: quick-reference
---

# Design Instrucional — Quick Reference

### Ordem macro de um guia

```
0-1  Contextualização  — o que será construído, glossário
2-N  Preparação        — instalação, autenticação, conceitos de plataforma
N+1..M Implementação   — 1 bloco = 1 resultado observável
M+1  Validação/produção — checklist final, guardrails
Apêndices              — comandos compilados, troubleshooting, FAQ
```

### Template de bloco (resumo)

```
Contexto      → por que este bloco agora
Conceito      → o "porquê" antes do "como" (sempre antes do código)
Implementação → comando/código + pegadinhas conhecidas
Verificação   → sinal concreto de que funcionou (número, print, teste)
Critério de aceite → checklist testável
```

### Checklist rápido de revisão de bloco

- [ ] Conceito vem antes de código?
- [ ] Um resultado observável por bloco (não vários)?
- [ ] Verificação dá sinal concreto, não "deve funcionar"?
- [ ] Pegadinhas conhecidas declaradas explicitamente?
- [ ] Critério de aceite é testável (checkbox, não prosa vaga)?

### Decision tree: este conteúdo vai em bloco principal ou apêndice?

```
É necessário para o leitor chegar ao objetivo final do guia?
    └── SIM → bloco principal, na ordem certa da jornada
    └── NÃO
        ├── É uma dúvida recorrente / erro comum que só alguns leitores encontram?
        │   └── SIM → apêndice de troubleshooting/FAQ
        └── É uma variação/alternativa ao caminho principal?
            └── SIM → nota dentro do bloco relevante ("alternativa: ...") ou apêndice
                       de configuração alternativa, nunca bloco principal extra
```

### Gotchas mais comuns (1 linha cada)

- Bloco de implementação sem "Conceito" força o leitor a copiar comando sem entender — sempre a
  causa raiz de "funcionou mas não sei por quê" nos comentários de guias reais.
- Glossário definido só no meio do guia (não no início) obriga o leitor a voltar páginas — sempre
  centralize antes do primeiro bloco de implementação.
- Critério de aceite tipo "deve estar funcionando" não é verificável — sempre peça um número,
  comando ou print específico.
- Guias com preparação > 50% do conteúdo total geralmente têm passos que deveriam virar apêndice
  ("setup alternativo") em vez de bloco principal.

Detalhe completo: ver `concepts/` e `patterns/` correspondentes.
