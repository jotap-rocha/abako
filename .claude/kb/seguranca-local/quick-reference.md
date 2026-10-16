---
domain: seguranca-local
topic: quick-reference
---

# Segurança local — Quick Reference

## Bloqueado para agentes (ADR 019, bloco A)

Ler ou escrever `.env`, pastas de dados e backups · comandos destrutivos fora do `tst` · push forçado · alterar visibilidade do repositório ou criar fork público · enviar dados a serviços externos · conectar-se a Postgres que não seja o contêiner dedicado do projeto.

## Pede confirmação (bloco B)

Migrações em `prd` · deploy local · instalar dependências · apagar arquivos · ler issues/PRs de terceiros (conteúdo não confiável).

## Checklist antes de entregar ao revisor externo

- [ ] `check` verde
- [ ] Sem dado real, `.env`, dump ou backup no pacote
- [ ] Sem ADRs no pacote (só rubrica + SPEC + código + testes)
- [ ] Varredura de termos pessoais limpa

## Checklist de aplicação web

- [ ] Toda consulta filtrada pelo `user_id` da sessão
- [ ] Senha Argon2id; nunca em log
- [ ] Cookie HttpOnly + SameSite; CSRF (Origin + token); CORS restrito
- [ ] Rate limit de login
- [ ] Nenhuma credencial bancária armazenada ou solicitada
