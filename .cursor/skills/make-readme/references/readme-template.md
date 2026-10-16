# Template do README.md gerado

Ler ao executar o Passo 2 do SKILL.md (gerar README). Preencher **apenas** o que foi
encontrado nas fontes — seção sem fonte = omitir, nunca "N/A" ou placeholder.

```markdown
# {nome do projeto}

> {tagline — 1 frase, extraída do CLAUDE.md ou README existente}

## O que é

{Parágrafo descrevendo o propósito. Fonte: CLAUDE.md ou README.md existente.}

## Stack

| Camada | Tecnologia |
|---|---|
{linhas extraídas do CLAUDE.md — seção Stack}

## Pré-requisitos

- Docker + Docker Compose
- {outros se declarados em CLAUDE.md ou pyproject.toml}

## Quickstart

```bash
# Subir todos os serviços
{comando extraído de CLAUDE.md — seção Comandos}

# Verificar saúde
{comando de health check se existir}
```

## Serviços

| Serviço | Porta | Descrição |
|---|---|---|
{extraído do docker-compose.yml — services e ports}

## Variáveis de ambiente

Copie `.env.example` para `.env` e preencha:

| Variável | Obrigatória | Descrição |
|---|---|---|
{extraído do .env.example}

## Estrutura do projeto

```
{tree de alto nível — extraído da estrutura de pastas, ignorando node_modules/.venv}
```

## Desenvolvimento

```bash
# Instalar dependências
{extraído de pyproject.toml / package.json}

# Rodar testes
{extraído de CLAUDE.md — seção Comandos}

# Lint / typecheck
{extraído de CLAUDE.md — seção Comandos}
```

## Decisões arquiteturais

{lista de ADRs em docs/adr/ — título e link apenas}

## Licença

{extraído de pyproject.toml / package.json / LICENSE — omitir se não encontrado}
```
