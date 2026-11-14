> **Este repositório é o projeto `abako`, não o Agent Harness Canônico.**
> Não copie o guia do repositório canônico do harness. Refine com `/grill-me`, `/grill-with-docs` ou `harness-architect`.

# Glossário de domínio — abako

> Derivado do brainstorm e dos ADRs 006–054. Refinar com /grill-with-docs.

## Domínio

Finanças pessoais de um único usuário (modelo já preparado com `user_id` para multiusuário futuro): saldos, gasto real, cartões com parcelas e terceiros, reserva, compromissos de curto prazo e uma conta de benefício (vale) tratada à parte.

## Termos do domínio

| Termo | Definição | Sinônimos | O que NÃO é |
|---|---|---|---|
| Ledger | Tabela de transações; edição cria nova versão (SCD2), exclusão é lógica | livro-caixa | Saldo guardado como número |
| Snapshot de saldo | Saldo informado pelo usuário (o que o app do banco mostra), checkpoint de conferência | foto do extrato | Correção do saldo |
| Saldo derivado | Último snapshot + transações válidas posteriores | saldo calculado | Saldo digitado |
| Divergência | Derivado ≠ snapshot; sinalizada (R4), nunca corrigida sozinha | | Erro corrigido automaticamente |
| Conta | Onde o dinheiro mora: corrente, reserva, investimento, benefício; cartão é conta de **dívida** (SPEC-005). Editar conta cria nova versão | | Linha de crédito |
| Conta do banco (conta-mãe) | Conta corrente a que uma reserva ou investimento pertence; a filha tem saldo próprio, separado da corrente | | Saldo somado |
| Caixinha / cofre | Reserva que pertence a um banco (cada banco usa um nome); guardar nela é uma transferência, não gasto | | Investimento, parte da conta corrente |
| Lançamento | Um registro do ledger por tipo (ADR 011/042): o valor é digitado positivo e o tipo dá o sinal; transferência e investimento têm duas pernas | transação | |
| Linha de crédito | Entidade que detém o limite; vários cartões a compartilham | teto | Cartão |
| Limite usado | Soma das dívidas dos cartões da linha, incl. parcelas futuras e terceiros; compra consome o valor total | | Soma das parcelas do mês |
| Competência | Mês da fatura a que a parcela pertence | | Data da compra |
| Gasto real | Despesa própria por parcela no mês da fatura | consumo | Pagamento de fatura, transferência, investimento, repasse, rendimento, terceiros, benefício |
| Transferência | Movimento entre contas em duas pernas com soma zero | | Gasto |
| Repasse | Terceiro devolvendo o que o usuário pagou por ele; abate o "a receber" | | Receita |
| A receber | Despesas de terceiros no cartão − repasses, por pessoa | fiado | Receita |
| Estorno | Integral (nenhuma parcela paga) ou com parcelas pagas (crédito na próxima fatura aberta) | | Dinheiro devolvido à conta corrente |
| Parcela paga | O que o pagamento solto do cartão cobre, alocado por competência, data da compra e parcela; paga em parte também conta, só na parte paga (ADR 044) | Parcela quitada (valor todo coberto) | Pagamento ligado a uma fatura |
| Reserva | Conta dedicada com meta = N meses × gasto essencial (N inicial 3) | | Parte de conta comum |
| Cobertura | Saldo da reserva ÷ gasto essencial, em meses | | |
| Rendimento | Tipo próprio de transação | | Receita comum |
| Recorrente / Ocorrência | Cadastro de fixo ou receita esperada / instância mensal, vinculável a uma transação (marca como paga) | | |
| Disponível (R2) | Saldos correntes + receitas recorrentes pendentes no horizonte do R2 (parâmetro, inicial 10 dias) | | Inclui reserva, vale ou crédito do vale |
| Compromissos (R2) | Fixos pendentes + faturas **próprias** com vencimento no horizonte | | Inclui terceiros |
| Sobra (R2) | Disponível − compromissos; alerta se < 0 | | |
| Conta de benefício | Conta cujas despesas não entram no gasto real nem na tela principal. Pode haver mais de uma | | Despesa comum |
| Vale | A conta de benefício de **refeição**: só ela tem bolsos, sobra e R5 | vale-refeição | Outra conta de benefício (ex.: alimentação), que não tem bolsos |
| Bolso | Divisão do vale (só o de refeição): trabalho / pessoal | envelope | |
| Base de trabalho | Parâmetro com vigência (inicial R$ 200); pessoal = crédito do mês − base | | |
| Sobra do vale | Σ max(resta, 0) por bolso, sem compensar estouro; decisão é evento com histórico e não move saldo | | Saldo do vale |
| Resta (do bolso) | Alocação efetiva do mês − consumo do bolso (trabalho ou pessoal); não acumula entre meses, só pela sobra decidida | saldo do bolso | Saldo da conta do vale |
| Estouro (do bolso) | Resta negativa de um bolso no mês corrente; dispara o alerta R5 e nunca é compensado com a sobra do outro bolso | | Saldo negativo da conta |
| Horizonte do R2 | Janela de dias (inicial 10, de 1 a 90, com vigência) em que o R2 olha receitas e compromissos; inclui hoje e hoje + horizonte | | Mês corrente |
| Aporte mensal | Quanto guardar por mês para a reserva chegar à meta até a data-alvo (opcional); arredonda para cima em centavos | | Rendimento |
| Vencimento do cartão | Dia de pagamento da fatura, cadastrado por cartão com vigência; maior que o dia de fechamento = mesmo mês da competência, senão o mês seguinte | data de pagamento | Dia de fechamento |
| Pessoa | Terceiro cadastrado (nome em claro só na sessão do dono, ADR 050); a compra é 100% própria ou 100% de uma pessoa | terceiro cadastrado | Usuário do sistema |
| Crédito da pessoa | Repasse que passou da dívida da pessoa; aparece separado, e o "a receber" nunca fica negativo | | Dinheiro do usuário |
| Analítico (pipeline) | Arquivo DuckDB só com agregados, regerado por inteiro de forma manual, fora do repositório, sem nome nem descrição | | Cópia do ledger |

## Acrônimos e siglas

| Sigla | Significado |
|---|---|
| ADR | Decisão registrada em `docs/adr/` |
| INV | Invariante testável em `tests/contracts/invariantes.yaml` |
| SPEC | Especificação de entrega, com critérios `SPEC-NNN-AC-N` |
| R1 | Alerta de reserva |
| R2 | Alerta de sobra no horizonte do R2 (parâmetro, inicial 10 dias) |
| R3 | Alerta de limite (adiado) |
| R4 | Lista de divergências derivado × snapshot |
| R5 | Alerta do vale por bolso: dispara quando o `resta` de um bolso (trabalho ou pessoal) fica negativo; o outro bolso não compensa |
| VR | Vale-refeição: a conta de benefício marcada como VR (com vigência) é a única com bolsos trabalho e pessoal, sobra e R5; o VA é outra conta de benefício, sem bolsos |
| R6 | Alerta de valores a receber (adiado) |
| R7 | Alerta de categoria fora do padrão (adiado) |
| SCD2 | Dimensão de variação lenta tipo 2 (histórico por vigência) |
| PWA | Web app instalável |

## Termos de engenharia / web

| Termo | Explicação |
|---|---|
| PWA | Site que o celular/PC instala como app (ícone, tela cheia) |
| Vite | Ferramenta que monta e serve o front-end durante o desenvolvimento |
| FastAPI | Framework Python que expõe as regras como API HTTP |
| OpenAPI | Contrato descrevendo todas as rotas da API; dele se gera o cliente TS |
| CORS | Regra do navegador sobre quais sites podem chamar sua API |
| CSRF | Ataque em que outro site faz seu navegador logado executar uma ação; defesa: SameSite, Origin e token |
| Cookie HttpOnly | Cookie que o JavaScript da página não consegue ler |
| SameSite | Cookie só viaja em requisições originadas do mesmo site |
| Argon2id | Algoritmo de hash de senha, lento de propósito |
| Rate limit | Limite de tentativas por tempo (barra força bruta no login) |
| gitleaks | Ferramenta que barra commit contendo segredo |
| Hook (pre-commit / PreToolUse) | Script que roda antes de um evento e pode bloqueá-lo |
| Hypothesis / RuleBasedStateMachine | Testes que geram casos e sequências de operações aleatórias para quebrar invariantes |
| DuckDB | Banco analítico em arquivo único, usado só para agregados (ADR 008) |
| Playwright | Robô que usa o navegador de verdade nos testes de ponta a ponta |
| Invariante | Afirmação que tem que ser sempre verdadeira, qualquer que seja o dado |
| Fixture | Conjunto de dados de entrada e resultado esperado conhecido |
| Runner (CI) | Máquina que executa o pipeline do GitHub Actions |
| Pin por SHA | Fixar uma ação do CI num commit exato, não numa tag mutável |

## Regras de negócio implícitas

- Tela principal mostra receita de **caixa**, gasto real, sobra R2 (fatura própria e total), reserva e alertas; o vale aparece só na sua página de métricas.
- Toda despesa do vale exige bolso (padrão sugerido: pessoal).
- Fechamento do cartão é cadastrado com vigência; competência é editável; erros iniciais se corrigem por edição.
- Editar compra parcelada recalcula só as parcelas não pagas.
- Importação futura de extratos deve ser idempotente (INV-16).
- v1 sem sandbox de dados: desenvolvimento usa dados reais por decisão do usuário (ADR 014).
