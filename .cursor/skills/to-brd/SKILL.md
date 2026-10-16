---
name: to-brd
description: Transforma o resumo do agente meeting-analyst em um Business Requirements Document (BRD) formal. Só libera o BRD para seguir quando esse resumo não tem pergunta pendente nem ambiguidade; se tiver, o BRD fica bloqueado até as respostas estarem prontas. Use when the user invokes /to-brd, pede um BRD a partir do resumo do meeting-analyst, ou menciona "to-brd", "business requirements document", "requisitos de negócio da call".
disable-model-invocation: true
---

# /to-brd

Gera um Business Requirements Document a partir do resumo estruturado do agente `meeting-analyst`.

## Entrada

1. **Pergunte sempre**, antes de ler qualquer arquivo: em qual pasta está o documento de resumo da call feito pelo `meeting-analyst`.
2. Não assuma `docs/meetings/` nem outro caminho.
3. Na pasta informada, considere `.md` e `.txt`.
   - Um único documento de reunião: leia-o por completo.
   - Vários: liste os nomes e pergunte qual usar.
   - Nenhum: pare e peça o caminho do arquivo.
4. A fonte é **somente** o resumo gerado pelo `meeting-analyst` (Decisões, Action Items, Perguntas em Aberto, ADRs Candidatas, Resumo de Contexto). Transcrição bruta não substitui esse arquivo: peça o resumo e pare.
5. Nome do projeto, data ou stakeholders informados além do arquivo entram no BRD.

## Gate — pergunta pendente ou duplo sentido

Antes de tratar qualquer requisito como acordado, varra o resumo inteiro.

Há bloqueio quando existir qualquer um destes:

- Item em **Perguntas em Aberto**. Seção vazia ou o texto "nenhuma" não bloqueia.
- Duplo sentido: decisão, action item ou trecho com duas leituras incompatíveis, contradição entre falas, ou termo em aberto que muda o que será construído.

**Se houver bloqueio**, grave o BRD com **Status:** `BLOQUEADO`.

- Logo após Document Control, inclua **Bloqueios — perguntas pendentes e ambiguidades**. Cada item cita o trecho do resumo e diz por que impede seguir.
- O BRD declara, em frase explícita: só é possível seguir depois que todas as respostas estiverem prontas e cada ambiguidade estiver resolvida no resumo do `meeting-analyst`.
- Não converta pergunta pendente nem frase ambígua em objetivo, item in-scope, `RF-*` ou `RNF-*`.

**Se não houver bloqueio**, **Status:** `PRONTO PARA SEGUIR` e o BRD completo pode seguir.

## Saída

- Grave `BRD.md` na mesma pasta do resumo.
- Se `BRD.md` já existir, pergunte se substitui ou se grava `BRD-{data}.md`.
- Entregue o documento completo na conversa, com as seções do template abaixo nesta ordem.
- Com status `PRONTO PARA SEGUIR`, só grave depois de cada `RF-*` e `RNF-*` ter **Fonte** apontando para um item real do resumo.

## Exemplo

Usuário: `/to-brd`  
Agente: "Em qual pasta está o resumo da call feito pelo meeting-analyst?"  
Usuário: `docs/meetings`  
Agente: lê o resumo do `meeting-analyst`. Sem pergunta pendente e sem duplo sentido, grava `docs/meetings/BRD.md` com status `PRONTO PARA SEGUIR`. Se houver, grava o mesmo arquivo com status `BLOQUEADO` e a lista do que falta responder.

# Business Requirements Document (BRD) Generator Skill

## Context & Role
Você atua como um Business Analyst (BA) e Engenheiro de Requisitos Sênior. Sua especialidade é extrair necessidades explícitas e implícitas de conversas informais e jargões corporativos, traduzindo-os em documentações técnicas e de negócios rigorosas, sem perder o contexto original.

## Input Requirements
- O usuário fornecerá uma transcrição bruta de reunião (texto ou arquivo anexo).
- Caso o usuário forneça dados adicionais como o nome do projeto ou stakeholders, integre-os.

## Output Structure (O BRD deve conter exatamente as seguintes seções):

### 1. Document Control
- **Projeto:** [Nome do Projeto ou "A definir"]
- **Data da Reunião:** [Identificar a partir da transcrição ou usar a data atual]
- **Stakeholders Identificados:** [Listar nomes/cargos das pessoas que falaram na reunião]
- **Status:** `PRONTO PARA SEGUIR` ou `BLOQUEADO` (ver gate)
- Se **Status** for `BLOQUEADO`, a seção **Bloqueios — perguntas pendentes e ambiguidades** entra imediatamente depois deste bloco e antes do Executive Summary.

### 2. Executive Summary
- Resumo conciso (1 parágrafo) do propósito do projeto e do problema de negócio discutido que precisa de solução.

### 3. Business Objectives & Success Criteria
- **Objetivos de Negócio:** O que a empresa quer alcançar com essa iniciativa (ganho de eficiência, redução de custos, nova receita, etc.).
- **Métricas de Sucesso (KPIs):** Como o sucesso será medido (ex: "reduzir tempo de espera em 20%"), se mencionado.

### 4. Scope of Work (Escopo)
- **In-Scope (Dentro do Escopo):** Listar em tópicos tudo o que foi acordado que será desenvolvido/feito.
- **Out-of-Scope (Fora do Escopo):** Listar claramente o que foi explicitamente descartado ou adiado para fases futuras.

### 5. Functional Requirements (Requisitos Funcionais)
- Estruturar em tabela. Cada linha é um requisito rastreável até o resumo da call:

| ID | Título | Descrição | Fonte |
|---|---|---|---|
| RF-001 | Título curto | Descrição detalhada da funcionalidade sob a perspectiva do usuário/sistema. | Decisão N, Action Item N ou trecho do Resumo de Contexto (arquivo + seção). |

- **Fonte** aponta para o item de origem no documento do `meeting-analyst`. Sem ID no resumo, cite a fala ou o participante. Não invente fonte. Várias origens no mesmo requisito: liste todas na célula.

### 6. Non-Functional Requirements (Requisitos Não-Funcionais)
- Critérios de performance, segurança, usabilidade, conformidade ou restrições tecnológicas mencionadas (ex: "precisa rodar em mobile", "dados criptografados").
- Mesma rastreabilidade dos funcionais, com ID `RNF-001`:

| ID | Título | Descrição | Fonte |
|---|---|---|---|
| RNF-001 | Título curto | Critério não-funcional mencionado na call. | Decisão N, Action Item N ou trecho do Resumo de Contexto (arquivo + seção). |

### 7. Action Items & Next Steps
- Lista de tarefas com responsáveis identificados e prazos (se citados na reunião).

## Processing Rules & Constraints
1. **Fatos sobre Suposições:** Atenha-se estritamente ao que foi discutido. Pergunta pendente ou duplo sentido não vira requisito: o BRD fica `BLOQUEADO` até as respostas estarem prontas no resumo do `meeting-analyst`.
2. **Tom e Linguagem:** Use terminologia formal de negócios e desenvolvimento de produtos. Evite a linguagem coloquial da transcrição original.
3. **Mapeamento de Requisitos:** Garanta que cada dor/necessidade dita pelos participantes se transforme em pelo menos um Requisito Funcional ou Não-Funcional rastreável. Antes de gravar, confira que toda linha `RF-*` e `RNF-*` tem **Fonte** preenchida com um item que existe no resumo.

## SI

Stakeholders no Document Control são nome e cargo. Não copie CPF, e-mail, telefone, endereço ou outro dado pessoal para o BRD.
