# PRD — abako

> **Atualizado em 2026-10-18**: incorpora D1..D8 da revisão adversarial (aprovadas; D2 parcial): SPECs reordenadas e renumeradas (001..014), gasto real com SPEC própria, PWA online, v1 sem compra dividida, backup com restauração testada, segurança local, concorrência/idempotência no esquema.

> PRD consolidado das decisões (ADRs 006–032), finalizado no `harness-design` (2026-10-19). Fica só local: não é publicado em issue tracker externo (repositório público, ADR 022). Cada SPEC é detalhada uma por vez, com critérios `SPEC-NNN-AC-N`.

## Problem Statement

O usuário confere o saldo das contas manualmente em planilha. Não consegue ver, num só lugar, quanto tem em cada banco, quanto realmente gastou no mês (sem transferências, pagamento de fatura, despesas de terceiros nem o vale) e se o orçamento dos próximos dias está apertado ou folgado. Faturas, parcelas, limite compartilhado entre cartões e valores a receber de familiares tornam a conta difícil de fazer à mão.

## Solution

Um sistema local que funciona como **ledger** de transações, com conferência por snapshot de saldo. Ele mostra saldos por conta, cartões (fatura aberta/fechada, limite usado da linha), gasto real, cobertura da reserva, sobra do horizonte (R2), divergências (R4) e uma página separada para o vale.

## User Stories

1. Como usuário, quero lançar uma transação manualmente com campos que mudam conforme o tipo, para registrar débito/pix, crédito, receita, transferência, investimento, repasse e rendimento.
2. Como usuário, quero editar uma transação e ver o histórico de versões, para corrigir erros sem perder a trilha.
3. Como usuário, quero excluir uma transação logicamente, para que ela deixe de contar sem sumir do histórico.
4. Como usuário, quero ver o saldo de cada conta, para saber quanto tenho em cada banco.
5. Como usuário, quero informar um snapshot de saldo e ver a divergência contra o saldo derivado, para conferir meus lançamentos sem que o sistema corrija nada sozinho.
6. Como usuário, quero ver o saldo de qualquer dia passado (com as correções feitas até hoje) e, em consulta de auditoria, o que o sistema sabia na época; um snapshot antigo que passe a divergir após edição retroativa é sinalizado pelo R4 (D1).
7. Como usuário, quero lançar uma compra parcelada e ter as parcelas distribuídas nas faturas certas, com a última absorvendo os centavos.
8. Como usuário, quero ver a fatura aberta e a fechada de cada cartão, com total = própria + terceiros.
9. Como usuário, quero ver o limite usado da linha de crédito (incluindo parcelas futuras e terceiros), para saber o que ainda posso gastar.
10. Como usuário, quero cadastrar o fechamento do cartão com vigência e ajustar a competência manualmente, para corrigir erros iniciais. Dia de fechamento inexistente no mês usa o último dia válido do mês (D2); a data real de cada cartão é calibrada por snapshot de fatura (pendência externa, ADR 013).
11. Como usuário, quero estornar uma compra (integral ou com parcelas pagas) e ver limite e fatura corretos, sem dinheiro indo à conta corrente.
12. Como usuário, quero marcar uma compra inteira como de terceiro (v1: 100% própria ou 100% terceiro, sem divisão) e registrar repasses, para saber quanto cada pessoa me deve; repasse maior que a dívida é tratado explicitamente (D5).
13. Como usuário, quero ver meu gasto real do mês, sem transferências, investimentos, repasses, rendimentos, pagamento de fatura, terceiros nem vale.
14. Como usuário, quero definir a meta da reserva em meses de gasto essencial e ver nível, falta e cobertura em meses.
15. Como usuário, quero ver o aporte mensal necessário até uma data-alvo da reserva.
16. Como usuário, quero cadastrar fixos e receitas recorrentes, ver a ocorrência de cada mês e vinculá-la a uma transação.
17. Como usuário, quero ver a sobra do horizonte do R2, inicial 10 dias e configurável (disponível − compromissos) e ser alertado se for negativa.
18. Como usuário, quero ver ocorrências vencidas e não vinculadas em lista separada.
19. Como usuário, quero uma página do vale com crédito, consumo por bolso, resta, sobra, decisão e saldo total, sem que o vale apareça na tela principal.
20. Como usuário, quero ser alertado quando o `resta` de um bolso do vale ficar negativo (R5), sem que o outro bolso compense.
21. Como usuário, quero decidir o destino da sobra do vale e que isso apenas ajuste a alocação do mês seguinte, sem mover saldo.
22. Como usuário, quero fazer login com senha e que cada consulta enxergue só os meus dados.
23. Como usuário, quero que as telas expliquem termos técnicos em linguagem direta.
24. Como usuário, quero instalar o app como PWA no navegador do mesmo PC e usá-lo online; não há lançamento offline na v1 (D8).
25. Como usuário, quero um comando local para criar usuários e recuperar a senha, sem cadastro público nem e-mail.
26. Como usuário, quero que o painel analítico leia só agregados, sem acesso às transações.
27. Como usuário, quero backup criptografado com restauração testada e retenção mínima definida, para não perder meus dados (D7).
28. Como usuário, quero que o servidor local rejeite requisições com `Host` inesperado, que o cache da PWA seja limpo no logout e saber que a senha não protege contra outro acesso à minha conta do Windows (D6).
29. Como usuário, quero que um duplo clique ou retry não crie lançamento duplicado e que duas edições simultâneas da mesma transação não se sobrescrevam em silêncio (D4).

## Implementation Decisions

Detalhadas nos ADRs 006–032. Resumo:

- **Ledger versionado** (SCD2), saldo derivado = snapshot + transações válidas posteriores (ADR 006).
- **Sete tipos de transação**, parcela por linha, limite pelo total da compra (ADR 011).
- **Postgres** com `NUMERIC`, data civil `America/Sao_Paulo`, `user_id` em toda tabela; regras financeiras em views/funções SQL (ADR 012, 015).
- **Analítico em DuckDB**, arquivo separado, só agregados, fluxo unidirecional (ADR 008).
- **FastAPI** com OpenAPI; cliente TS gerado; **React + TS** como PWA; **Postgres** transacional (ADR 015).
- **Autenticação** própria: Argon2id, sessão no servidor, CSRF, CORS, rate limit (ADR 020).
- **Plataforma local** em `localhost`, bancos `prd`/`tst` mais um banco descartável só para o teste de restauração (ADR 014, 032).
- **Reserva, R2, recorrentes e vale** conforme ADR 023.

Decisões da revisão adversarial (aprovadas em 2026-10-18; detalhe em `01-grill.md`):

- **Edição retroativa (D1):** histórico exibido = visão corrigida; visão "conhecida na época" por auditoria (data de registro do SCD2); snapshot que passa a divergir é sinalizado pelo R4.
- **Fechamento (D2):** dia inexistente no mês = último dia válido; compra no próprio dia do fechamento definida na SPEC-005. Datas reais dos cartões: pendência externa, sem bloquear.
- **Concorrência/idempotência (D4)** como garantia de **esquema na SPEC-001**: unicidade parcial da versão vigente, campo de versão (controle otimista), chave de idempotência na criação; trava `pg_advisory_lock` no pipeline (SPEC-014).
- **Compra dividida (D5):** v1 só 100% própria ou 100% terceiro; repasse maior que a dívida tratado na SPEC-007.
- **Segurança local (D6):** validação de `Host`, limpeza do cache da PWA no logout, limite declarado do que a senha protege (SPEC-002 e SPEC-012).
- **Backup (D7):** criptografado (age), restauração testada e retenção mínima dentro da v1 (SPEC-001 define o procedimento; teste de restauração no `check` ou rotina de deploy local).
- **PWA (D8):** instalável, no navegador do mesmo PC (`127.0.0.1`), online, sem lançamento offline. Acesso por celular/rede local/externa é pretendido no futuro e exige ADR próprio (ADR 031).

Ordem das entregas (cada SPEC sai uma por vez, com critérios `SPEC-NNN-AC-N`). Login vem antes de qualquer rota financeira; pipeline por último:

| SPEC | Entrega | Era |
|---|---|---|
| 001 | Esquema base, papéis, banco `tst`, fixtures, `check`, garantias de concorrência/idempotência, procedimento de backup | 001 |
| 002 | Login, sessão, isolamento por `user_id` da sessão, validação de `Host`, CSRF/CORS/rate limit | 008 |
| 003 | Saldo derivado + snapshot + R4 (cálculo), semântica de edição retroativa | 002 |
| 004 | Lançamento manual por tipo + edição versionada (idempotência, controle otimista) | 003 |
| 005 | Faturas, parcelas e linha de crédito (fechamento com vigência, dia inexistente, dia do fechamento) | 004 |
| 006 | Estorno | 005 |
| 007 | Terceiros e repasse (100% próprio ou 100% terceiro; repasse > dívida) | 006 |
| 008 | Gasto real (exclusões: transferência, investimento, repasse, rendimento, pagamento de fatura, terceiros, conta de benefício) | novo |
| 009 | Reserva / cobertura | 007 |
| 010 | Recorrentes + R2 (cálculo da sobra) | 012 |
| 011 | Alertas R1, R2, R4 | 011 (sem R5) |
| 012 | Frontend (PWA online, logout limpa cache, textos explicativos) | 010 |
| 013 | Vale (bolsos, sobra, decisão) + alerta R5 | 013 + R5 |
| 014 | Pipeline / analítico (DuckDB, trava de execução) | 009 |

Racional da ordem: gasto real (008) depende de faturas, estorno e terceiros prontos; R2 (010) precisa dos recorrentes e vem antes do alerta (011); o frontend (012) consome tudo que é anterior, e a tela do vale nasce com a 013; o analítico é o último por ser o mais adiável (ADR 008).

**Migração das invariantes** (campo `spec` de `tests/contracts/invariantes.yaml`): INV-01→004; INV-02→005; INV-03→003; INV-04→008; INV-05→008; INV-06→005; INV-07→005; INV-08→006; INV-09→004; INV-10→007; INV-11→008 (parte de limite/fatura testada em 005/007); INV-12→009; INV-13 fica em 001 (esquema) com teste de sessão na 002; INV-14→001; INV-15→014; INV-16→futura; INV-17→009; INV-18→010; INV-19→010; INV-20→008; INV-21→013; INV-22→013; INV-23→003; INV-24→013; INV-25→013; INV-26→005 (uso pelo R2 na 010); INV-27→001; INV-28→004; INV-29→004; INV-30→003; INV-31→005; INV-32→007; INV-33→007 (regra exata fixada na 007); INV-34→002; INV-35→014. Concorrência/idempotência: o esquema nasce na 001 e o comportamento é testado na 004.

## Testing Decisions

- Teste só comportamento externo; regra financeira é testada com as fixtures de `fixtures/numericos.yaml`, com valores esperados calculados à mão (sem tautologia).
- Ferramentas: pytest (SQL + backend), Hypothesis incl. `RuleBasedStateMachine` para invariantes numéricas, Vitest + RTL, Playwright (poucas jornadas), testes dos hooks/gitleaks.
- Toda invariante (`tests/contracts/invariantes.yaml`) e todo critério (`tests/contracts/criterios.yaml`) tem teste; um script de rastreabilidade falha se faltar algum.
- A suíte aborta se a conexão de banco não for a de `tst`.
- Comando único `check`; o revisor adversarial só recebe entrega com `check` verde (ADR 017, 021).

## Out of Scope

Lançamento ou uso offline da PWA (v1 é online, em `127.0.0.1`) · compra dividida entre próprio e terceiro (v1: 100% de um ou de outro) · direito ao esquecimento (backup e retenção mínima entram na v1) · pipeline disparado por evento e série histórica no analítico (v1 manual, só agregados) · proteção contra outro acesso à conta do Windows do usuário (a senha não cobre isso; declarado) · SLA formal de desempenho/disponibilidade · Multiusuário funcional · múltiplas moedas · Open Finance e scraping · leitura de PDF e canal de e-mail/WhatsApp · app nativo e SSR · hospedagem e acesso externo/celular/rede local (pretendido no futuro; ADR 031) · juros de parcelamento e câmbio · chargeback e estorno parcial por item · alertas R3, R6, R7 · projeção além do horizonte do R2 · categorização automática do essencial · 2FA/SSO · streaming e lakehouse · CD automático.

## SI Considerations

SI Assessment nível c; `[AVISO_LGPD]` (dado financeiro pessoal real, sem ambiente sintético: risco aceito, ADR 014).

- **Finalidade única:** controle financeiro pessoal do próprio usuário.
- **`prd` somente leitura para o agente**; escrita só em `tst`; migração em `prd` pede confirmação humana (ADR 019). O agente não lê `.env`, dados, backups nem `.duckdb`/`.age` (ADR 024).
- **Isolamento:** `user_id` em toda tabela, filtrado pelo `user_id` da sessão (INV-13); a aplicação não tem `UPDATE/DELETE` nas tabelas de versão do ledger.
- **Autenticação:** Argon2id, sessão no servidor, CSRF, CORS, rate limit, validação de `Host`; serviços só em `127.0.0.1` (ADR 020, 031). A senha não protege contra outro acesso à conta do Windows (declarado).
- **Segredos e backup:** `.env` fora do git, gitleaks no pre-commit e no CI; backup criptografado (age) com restauração testada em banco descartável, nunca sobre `prd` (ADR 018, 032).
- **Sem credencial bancária** (ADR 010); entrada manual na v1.
- **Logs e URLs** sem PII, valores ou senha; pacote do revisor sem dado real, `.env`, dumps ou backups (ADR 017).
- **Direito ao esquecimento** fora da v1; ciclo de vida cobre exclusão física do banco e expiração de backups.

## Further Notes

- Sem SLA formal de desempenho ou disponibilidade; qualquer necessidade futura é tratada como evolução contínua.
- Pendências externas: formatos de exportação dos bancos, bruto vs. líquido da reserva, datas de fechamento e semântica de limite dos cartões, disponibilidade do modelo revisor.
- Alertas da v1: R1 (reserva), R2 (sobra no horizonte), R4 (divergência) na SPEC-011; R5 (`resta` negativo em bolso do vale) na SPEC-013, junto do vale. R4 é alerta visível no app, não só log.
- Pendências externas: a data real de fechamento de cada cartão o usuário não sabe hoje; cadastro com vigência, ajustável e calibrado por snapshot de fatura (ADR 013); não bloqueia nenhuma SPEC. Origem do "gasto essencial" da reserva segue pendente.
