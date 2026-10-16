# Instalação do Agent Harness Canônico V2 — Projeto do Zero (Spark Local)

**Gravação:** `install canônico local e databricks-20260824_103916`  
**Data:** 24 de agosto de 2026, 13:39  
**Duração:** 7m 29s  
**Autor:** João Pedro Rocha  

---

## Objetivo

Demonstrar de forma objetiva como instalar o **Agent Harness Canônico V2** em um **projeto novo (pasta vazia)**, voltado inicialmente para **desenvolvimento local Spark**. Este é o **vídeo 1 de 2**; o segundo vídeo cobrirá a evolução do mesmo projeto para **Databricks**.

---

## O que é o Agent Harness Canônico V2?

O Agent Harness Canônico V2 é um **instalador** que padroniza a estrutura de arquivos em projetos novos ou já existentes, alinhada ao ambiente **Katu/Carelo** para:

- Desenvolvimento apoiado por **LLMs**
- Projetos **agênticos** (criação de requisitos, definição de funcionalidades e tarefas)
- Fluxos, contextos e **guardrails** já configurados para o ambiente da equipe

Funciona como **instalador**: copia e configura artefatos do repositório canônico no projeto de destino.

---

## Pré-requisitos

| Item | Detalhe |
|------|---------|
| Repositório canônico | **Agent Harness Canônico V2** no Azure DevOps |
| Acesso | Wiki → Files → buscar `agent harness canônico V2` → **Clone** |
| Pasta de destino | Projeto vazio (ex.: `Databricks Mapa Corporativa`) |
| Leitura obrigatória | `docs/manuais/install-harness-cli.md` ou `docs/manuais/como-usar.md` na raiz do canônico |

---

## Passo a passo — Instalação (projeto do zero)

### 1. Clonar o repositório canônico

```bash
git clone <URL-do-repositório-canônico-V2>
cd agent-harness-canonico-v2
```

> A URL exata deve ser obtida na wiki do Azure DevOps (Files → Agent Harness Canônico V2 → Clone).

### 2. Preparar a pasta de destino

- Criar uma pasta **vazia** para o novo projeto.
- Exemplo usado na gravação: `Databricks Mapa Corporativa` (será reutilizada no vídeo 2 para Databricks).
- Se o projeto fosse **somente Spark local**, a instalação terminaria nesta etapa.

### 3. Executar o instalador

Na **raiz do repositório canônico**, ler a documentação de instalação e executar:

```bash
./install-harness
```

### 4. Opções do wizard

| Opção | Uso |
|-------|-----|
| **1 — Criar projeto do zero** | Pasta vazia, sem arquivos pré-existentes |
| **2 — Trazer harness para projeto existente** | Projeto já com código; o instalador tenta detectar a stack |

**Neste vídeo:** opção **1** (projeto zerado).

### 5. Caminho de destino

Informar o caminho absoluto ou relativo da pasta vazia criada no passo 2.

### 6. Stack não detectada

Com pasta vazia, **não há stack detectada**. Recomendação da gravação:

- Marcar **“Forçar todas as categorias sem stack detectada”** para prosseguir com a instalação padrão.

> Em projeto existente, o instalador tentaria detectar Spark local, Databricks, etc.

### 7. Confirmar o plano de instalação

O instalador exibe um resumo (~120 itens) do que será copiado. Modelo base: **`.claude/`**, com espelhamento automático para **`.cursor/`**.

Confirmar para concluir a instalação.

---

## Resultado esperado

Após instalação bem-sucedida, a pasta de destino deve conter, entre outros:

| Artefato | Descrição |
|----------|-----------|
| `.claude/` | Agents, commands, design, dev loop, SDDs, projetos, fluxos |
| `.cursor/` | Espelho para uso no Cursor |
| Documentação | Guias de uso, passo a passo, comandos do harness |

---

## Documentação recomendada (pós-instalação)

Ler os arquivos gerados no **canônico** e no **destino**:

- **docs/manuais/como-usar.md** / guia passo a passo
- **docs/manuais/harness-guide.md**: comandos disponíveis
- Fluxos: **brainstorm**, **design**, **define**, **grill**, **tasks**, etc.

> Familiaridade com esses materiais acelera o uso do harness no dia a dia.

---

## Escopo deste vídeo vs. próximo vídeo

| Parte | Conteúdo |
|-------|----------|
| **Vídeo 1 (este)** | Instalação em projeto vazio — perfil **Spark local** |
| **Vídeo 2 (próximo)** | Evoluir o projeto `Databricks Mapa Corporativo` para repositório **Databricks** (conceito DE / engenharia de dados) |

---

## Resumo em uma linha

> Clone o canônico V2 → pasta vazia → `./install-harness` → opção 1 → informar destino → forçar categorias sem stack → confirmar → revisar `.claude/`, `.cursor/` e documentação.

---

## Tags sugeridas (wiki)

`agent-harness` `v2` `install-harness` `spark-local` `katu` `carelo` `llm` `onboarding`
