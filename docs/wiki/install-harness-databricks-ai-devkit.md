# Instalação do AI DevKit Databricks — Evolução do Projeto de Destino (Parte 2)

**Gravação:** `install canônico local e databricks-20260824_105637`  
**Data:** 24 de agosto de 2026, 13:56  
**Duração:** 11m 55s  
**Autor:** João Pedro Rocha  

---

## Objetivo

Continuar a instalação iniciada na **Parte 1**, evoluindo o projeto de destino **Databricks Mapa Corporativa** para receber o **AI DevKit Databricks**. O projeto passa a suportar:

- Desenvolvimento **Databricks local**
- Desenvolvimento **Spark local**
- Desenvolvimento **Databricks no Azure**

> **Pré-requisito:** assistir e executar a [Parte 1](install-harness-projeto-zero-spark-local.md) (instalação do Harness Canônico V2 em pasta vazia).

---

## Visão geral do fluxo

```
Parte 1 (Harness Canônico V2)  →  Parte 2 (AI DevKit Databricks)
         ↓                                    ↓
   .claude/ + .cursor/              .cursor/skills/ (Databricks)
   agents, SDD, fluxos              skills DE, ML, análise, apps
```

---

## Pré-requisitos

| Item | Detalhe |
|------|---------|
| Parte 1 concluída | Pasta de destino já com Harness Canônico instalado |
| Python | **3.12** ou superior (obrigatório para o AI DevKit) |
| Databricks CLI | Versão **1.8** ou superior |
| Repositório AI DevKit | **ai-devkit-core** no Azure DevOps |
| Ambiente virtual | `.venv` na pasta de destino do projeto |
| Leitura obrigatória | Documentação de instalação do AI DevKit (vídeo/README na raiz do repositório) |

---

## Passo 1 — Ambiente virtual Python 3.12

O AI DevKit exige um **ambiente virtual** com **Python 3.12**. Criar na pasta de destino (`Databricks Mapa Corporativa`).

### Verificar versão do Python

```bash
python --version
```

Deve retornar **3.12.x**. Se a versão global não for 3.12:

```bash
pyenv local 3.12.13
python --version   # validar novamente
```

### Criar e ativar o venv

```bash
cd /caminho/para/Databricks-Mapa-Corporativa
python -m venv .venv
source .venv/bin/activate
```

---

## Passo 2 — Clonar o AI DevKit

1. Acessar **Azure DevOps → Files**
2. Pesquisar por **`AI DevKit`**
3. Selecionar o repositório **`ai-devkit-core`**
4. Clonar com a URL gerada (credenciais do Azure DevOps quando solicitado)

```bash
git clone <URL-do-ai-devkit-core>
```

---

## Passo 3 — Executar o instalador no projeto de destino

> **Ponto crítico:** o `install.sh` deve ser invocado **a partir da pasta de destino** (não da raiz do clone do DevKit).

Na pasta **Databricks Mapa Corporativa**:

```bash
/caminho/do/clone/ai-devkit-core/install.sh
```

O instalador faz varredura de pré-requisitos (Git, Databricks CLI ≥ 1.8, etc.).

---

## Passo 4 — Opções do wizard

### IDE de desenvolvimento

O instalador faz **discovery** do ambiente e detecta IDEs já usadas (Cursor, Copilot, Codex, etc.). Escolher a IDE em uso — na gravação: **Cursor / Copilot**.

### Profile Databricks

| Opção | Recomendação |
|-------|--------------|
| Profile | **`default`** |

### Tipo de instalação

| Opção | Quando usar |
|-------|-------------|
| **Por projeto** | **Sempre** (escopo na pasta do projeto) |
| Global | Não usar — configura em nível de servidor |

### Skills do Databricks

Marcar **todas as skills** para cobrir evoluções futuras do projeto:

- Engenharia de dados (DE)
- Análise de negócios
- AI e machine learning
- Desenvolvimento de aplicação customizável

### Confirmação

Revisar o resumo (IDE, profile, escopo por projeto, skills). Confirmar — arquivos existentes serão **sobrescritos**.

---

## Resultado esperado

Após instalação bem-sucedida, comparar a árvore de pastas **antes e depois**:

| Local | Conteúdo novo |
|-------|---------------|
| `.cursor/skills/` | Skills com prefixo **`databricks-`** (DE, AI, funções, runtime, dashboards, etc.) |
| `.cursor/skills/` (já existentes) | Skills do **Harness Canônico V2** (sem prefixo Databricks) |
| Raiz / auxiliares | Artefatos de suporte criados pelo instalador do DevKit |

O projeto fica **híbrido**:

- **Harness Canônico V2** — processos agênticos (SDD, agents, fluxos, guardrails Katu/Carelo)
- **AI DevKit Databricks** — skills e práticas de desenvolvimento orientado ao Databricks

---

## Quando instalar o quê?

| Cenário | Instalação recomendada |
|---------|------------------------|
| Somente **Spark local** | Apenas **Parte 1** (Harness Canônico) |
| Somente **Databricks** | Apenas **AI DevKit** (sem Harness Canônico) |
| **Spark + Databricks** (híbrido) | **Parte 1 + Parte 2** (como na gravação) |

> Os dois instaladores juntos deixam o projeto mais completo, porém mais amplo. Para Databricks exclusivo, o AI DevKit sozinho já atende desenvolvimento orientado às melhores práticas Databricks.

---

## Resumo em uma linha

> Parte 1 feita → Python 3.12 + `.venv` na pasta destino → clone `ai-devkit-core` → `./install.sh` **na pasta destino** → IDE Cursor → profile `default` → instalação **por projeto** → todas as skills → confirmar → revisar `.cursor/skills/` (Harness + `databricks-*`).

---

## Tags sugeridas (wiki)

`agent-harness` `v2` `ai-devkit` `databricks` `spark-local` `python-3.12` `venv` `cursor` `onboarding`
