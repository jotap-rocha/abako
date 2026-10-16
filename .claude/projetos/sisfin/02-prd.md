# PRD — sisfin

> Rascunho consolidado das decisões (ADRs 006–023). Será refinado pelo `harness-design` / `/to-prd` depois do grill.

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
6. Como usuário, quero ver o saldo de qualquer dia passado, para auditar o histórico.
7. Como usuário, quero lançar uma compra parcelada e ter as parcelas distribuídas nas faturas certas, com a última absorvendo os centavos.
8. Como usuário, quero ver a fatura aberta e a fechada de cada cartão, com total = própria + terceiros.
9. Como usuário, quero ver o limite usado da linha de crédito (incluindo parcelas futuras e terceiros), para saber o que ainda posso gastar.
10. Como usuário, quero cadastrar o fechamento do cartão com vigência e ajustar a competência manualmente, para corrigir erros iniciais.
11. Como usuário, quero estornar uma compra (integral ou com parcelas pagas) e ver limite e fatura corretos, sem dinheiro indo à conta corrente.
12. Como usuário, quero marcar despesas como de terceiros e registrar repasses, para saber quanto cada pessoa me deve.
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
24. Como usuário, quero instalar o app como PWA no navegador.
25. Como usuário, quero um comando local para criar usuários e recuperar a senha, sem cadastro público nem e-mail.
26. Como usuário, quero que o painel analítico leia só agregados, sem acesso às transações.

## Implementation Decisions

Detalhadas nos ADRs 006–023. Resumo:

- **Ledger versionado** (SCD2), saldo derivado = snapshot + transações válidas posteriores (ADR 006).
- **Sete tipos de transação**, parcela por linha, limite pelo total da compra (ADR 011).
- **Postgres** com `NUMERIC`, data civil `America/Sao_Paulo`, `user_id` em toda tabela; regras financeiras em views/funções SQL (ADR 012, 015).
- **Analítico em DuckDB**, arquivo separado, só agregados, fluxo unidirecional (ADR 008).
- **FastAPI** com OpenAPI; cliente TS gerado; **React + TS** como PWA; **Postgres** transacional (ADR 015).
- **Autenticação** própria: Argon2id, sessão no servidor, CSRF, CORS, rate limit (ADR 020).
- **Plataforma local** em `localhost`, bancos `prd`/`tst` (ADR 014).
- **Reserva, R2, recorrentes e vale** conforme ADR 023.

Ordem das entregas (cada SPEC sai uma por vez, com critérios `SPEC-NNN-AC-N`):

| SPEC | Entrega |
|---|---|
| 001 | Esquema base, papéis, banco `tst`, fixtures |
| 002 | Saldo derivado + snapshot |
| 003 | Lançamento manual por tipo + edição versionada |
| 004 | Faturas, parcelas e linha de crédito |
| 005 | Estorno |
| 006 | Terceiros e repasse |
| 007 | Reserva / cobertura |
| 008 | Login |
| 009 | Pipeline / analítico |
| 010 | Frontend |
| 011 | Alertas |
| 012 | Recorrentes (+ R2) |
| 013 | Vale (bolsos, sobra) |

## Testing Decisions

- Teste só comportamento externo; regra financeira é testada com as fixtures de `fixtures/numericos.yaml`, com valores esperados calculados à mão (sem tautologia).
- Ferramentas: pytest (SQL + backend), Hypothesis incl. `RuleBasedStateMachine` para invariantes numéricas, Vitest + RTL, Playwright (poucas jornadas), testes dos hooks/gitleaks.
- Toda invariante (`tests/contracts/invariantes.yaml`) e todo critério (`tests/contracts/criterios.yaml`) tem teste; um script de rastreabilidade falha se faltar algum.
- A suíte aborta se a conexão de banco não for a de `tst`.
- Comando único `check`; o revisor adversarial só recebe entrega com `check` verde (ADR 017, 021).

## Out of Scope

SLA formal de desempenho/disponibilidade · Multiusuário funcional · múltiplas moedas · Open Finance e scraping · leitura de PDF e canal de e-mail/WhatsApp · app nativo e SSR · hospedagem e acesso externo · mobile fora da rede local na v1 · juros de parcelamento e câmbio · chargeback e estorno parcial por item · alertas R3, R6, R7 · projeção além do horizonte do R2 · categorização automática do essencial · 2FA/SSO · streaming e lakehouse · CD automático.

## Further Notes

- Sem SLA formal de desempenho ou disponibilidade; qualquer necessidade futura é tratada como evolução contínua.
- Pendências externas: formatos de exportação dos bancos, bruto vs. líquido da reserva, datas de fechamento e semântica de limite dos cartões, disponibilidade do modelo revisor.
- Alertas da v1: R1 (reserva), R2 (sobra no horizonte), R4 (divergência) e R5 (`resta` negativo em bolso do vale).
