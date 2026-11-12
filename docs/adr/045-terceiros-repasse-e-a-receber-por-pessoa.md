# 045 — Terceiros, repasse e "a receber" por pessoa: convenções da SPEC-007

**Status:** Aceita
**Data:** 2026-11-12
**Autores:** time
**Reversibilidade:** difícil

---

## Contexto

O ADR 009 criou o conceito (despesa de terceiro fora do gasto real, mas dentro do limite e da
fatura; repasse como tipo próprio) e o ADR 030 fixou "compra 100% própria ou 100% de terceiro",
deixando a regra do repasse excedente para esta SPEC. O ADR 043 (item 8) adiou para cá a fatura
"própria + terceiros" e o limite com terceiros. O ADR 044 define estorno e a alocação do pago, que
esta SPEC precisa respeitar. Decisões do usuário em 2026-11-12 (itens 1 a 7); os itens 8 a 14 são
pontos novos decididos na modelagem, para o usuário vetar se discordar.

## Decisão

1. **Terceiro só em compra no cartão (`credito`).** Débito, receita, transferência e demais tipos
   não levam pessoa. Cada compra é 100% própria (sem pessoa) ou 100% de uma pessoa; divisão é
   rejeitada (INV-32, fecha o ADR 030). No banco isso é estrutural: a compra tem **uma** pessoa
   (`pessoa_id` igual em todas as parcelas, conferido pelo gatilho de pernas) e a função de escrita
   recebe um único `p_pessoa`; a API recusa com 422 qualquer corpo que tente repartir.
2. **Cadastro mínimo de pessoa:** tabela `pessoa` com `user_id`, `pessoa_id` lógico, versão,
   `vigente` e `excluida`, como as demais entidades (ADR 006). Nome de 1 a 80 caracteres, único por
   usuário sem diferenciar maiúsculas entre as pessoas vigentes. A compra de terceiro aponta para a
   pessoa por `transacao_versao.pessoa_id` (sem chave estrangeira, como `conta_id`: os ids se repetem
   entre versões; a integridade vem das funções de escrita). Escrita só por `pessoa_gravar` e
   `pessoa_excluir`. Excluir a pessoa é recusado enquanto houver compra ou repasse vigente dela.
3. **Repasse = tipo próprio de lançamento** (`repasse`): entrada de valor positivo em **conta
   corrente** (nunca em reserva, investimento, benefício ou cartão), com pessoa obrigatória e data
   até hoje. Sobe o saldo da conta pelo mecanismo normal (ADR 041), **não é receita** (INV-12) e
   **não é gasto real** (INV-04). Edita e exclui como os demais lançamentos (versão, exclusão
   lógica); não tem vínculo com fatura nem compra.
4. **A receber por pessoa (INV-10):** para cada pessoa, `D` = soma do **total** das compras dela,
   com parcelas futuras (como no limite, INV-06), sem as compras estornadas; `R` = soma dos
   repasses vigentes dela. A visão devolve `divida = D`, `repassado = R`,
   `a_receber = max(D − R, 0)` e `credito_da_pessoa = max(R − D, 0)`. Tudo derivado a cada
   consulta; nada é gravado.
5. **Repasse maior que a dívida é aceito (INV-33, fecha o ADR 030):** o excedente aparece como
   `credito_da_pessoa`, nunca como "a receber" negativo. Uma compra futura da pessoa abate o crédito
   sozinha (D cresce e a diferença D − R é a mesma conta). Vale `D − R = a_receber − credito_da_pessoa`
   e `a_receber × credito_da_pessoa = 0`.
6. **Estorno de compra de terceiro** (ADR 044): a compra deixou de existir, então **D cai pelo T
   inteiro** (a compra estornada sai da dívida da pessoa). O crédito P do estorno continua sendo
   abatimento financeiro do cartão do usuário e não altera D nem R. Se a pessoa já tinha repassado
   mais que a nova D, o excedente vira `credito_da_pessoa` (item 5). O cartão com estorno continua
   imutável (ADR 044 item 9): não se edita nem exclui lançamento já gravado nele; a compra com parte
   paga não é editável nem excluível (ADR 044 item 8), vale ou não para terceiros.
7. **Fatura e limite (INV-11, INV-26):** a despesa de terceiro **entra** no total da fatura e no
   limite usado. O total da fatura é `própria + terceiros` e `fatura_total` não muda; a nova
   `fatura_resumo` devolve `total`, `propria` e `terceiros`. `fatura_itens` ganha a coluna final
   `pessoa_id` (nula = própria). O limite não é repartido: o pagamento do cartão é do cartão e a
   alocação do pago (ADR 044) não distingue própria de terceiros.
8. **Crédito do estorno na fatura segue a compra estornada (decisão nova):** o crédito P de um
   estorno aparece, na fatura, no mesmo grupo da compra (própria ou terceiros). Assim a fatura
   própria, que alimenta o R2 (INV-18, SPEC-010), não é reduzida por um estorno de compra de terceiro,
   e `total = própria + terceiros` continua valendo. A fatura de terceiros pode, por isso, ficar
   negativa na competência do crédito.
9. **Gasto real (SPEC-008):** a view `parcela_ativa` ganha `pessoa_id`; o gasto real filtra
   `pessoa_id IS NULL` (INV-11) e já não conta o tipo `repasse` (INV-04). Esta SPEC não calcula gasto
   real.
10. **Compras anteriores à 0008** ficam com `pessoa_id` nulo, ou seja, próprias (é o que já eram).
11. **Trocar a pessoa de uma compra** é uma edição comum da compra (nova versão, regras do ADR 044).
    Na prática só vale enquanto a compra não tem parte paga e o cartão não tem estorno.
12. **Assinatura pública:** `lancamento_gravar` ganha o 15º parâmetro `p_pessoa bigint DEFAULT NULL`;
    quem chamava com 14 argumentos continua funcionando (mesmo padrão do ADR 043). A função de escrita
    interna (`*_base`) passa a ter o mesmo parâmetro e o guarda do estorno (ADR 044) segue na frente.
13. **Mensagens de erro:** literais, sem interpolar nome, valor ou id (teste estático sobre o SQL da
    0008, como na 0007). Erros: `AB404` pessoa inexistente, `AB409` versão desatualizada, `AB410` nome
    repetido, `AB422` regra violada.
14. **Papéis:** `abako_app` lê `pessoa` e escreve só pelas funções; `abako_pipeline` lê tudo, **menos a
    coluna `nome`** (privilégio por coluna), para o nome de terceiro não ter como chegar ao analítico.
    A descrição livre do lançamento continua sendo texto do usuário (ADR 030) e é tratada como dado
    pessoal: fora de logs e do analítico.

## Consequências

- Migração 0008: tabela `pessoa`, coluna `transacao_versao.pessoa_id` com `CHECK` (repasse exige
  pessoa; compra aceita; os demais tipos não), sinal do repasse (> 0), views com `pessoa_id` no fim,
  gatilho de pernas conferindo uma pessoa por compra, `lancamento_gravar`/`lancamento_gravar_base`
  com o 15º parâmetro, `lancamento_excluir_base` copiando `pessoa_id`, `pessoa_gravar`,
  `pessoa_excluir`, `a_receber_pessoas`, `fatura_resumo` e `fatura_itens` com `pessoa_id`.
- O downgrade é recusado se existir pessoa, repasse ou compra com pessoa (apagaria dados).
- O banco continua sem "repasse acima da dívida" como erro: a API só precisa mostrar o crédito.
- Pendente de API (fin-backend): rotas de pessoa (criar, editar, excluir, listar), campo `pessoa` na
  compra, lançamento `repasse`, leitura de "a receber por pessoa" e da fatura com própria/terceiros,
  e a recusa de divisão no corpo da requisição.

## Alternativas consideradas

- Rejeitar repasse acima da dívida ❌: o usuário recebe o dinheiro de qualquer jeito (adiantamento);
  recusar deixaria o saldo da conta diferente do banco real.
- Gravar o saldo "a receber" ❌: seria dado derivado duplicado, sujeito a divergir (INV-03).
- `pessoa` como texto livre na transação (ADR 009, opção C original) ❌: nome repetido em toda
  linha, sem isolamento do dado pessoal e sem como excluir logicamente.
- Repartir o limite usado entre própria e terceiros ❌: o pagamento é do cartão; qualquer repartição
  seria arbitrária.
- Crédito do estorno sempre na fatura própria ❌: reduziria a sobra do R2 por uma compra que nunca
  entrou nela.

## Fora de escopo

Cobrança automática; terceiros com acesso ao sistema (revisar o ADR 009 se isso mudar); divisão de
compra; repasse vinculado a uma compra ou fatura; repasse em conta de benefício.

## Como verificar

INV-10, 11 (parte limite/fatura em INV-06 e INV-26), 26, 32, 33; fixtures F-FAT-01, F-LIM-01,
F-REP-01 a F-REP-04; critérios SPEC-007-AC-1 a AC-11.

## Impacto em SI/LGPD

Nome de terceiro é dado pessoal. Fica apenas em `pessoa.nome` (banco transacional), com `user_id` e
filtro pela sessão (INV-13). Nunca em log, em URL, em mensagem de erro nem no analítico: o pipeline
não tem SELECT na coluna `nome` e as funções de a receber e de fatura devolvem só `pessoa_id`; o nome
é resolvido na borda da API, por usuário. A aplicação não ganha UPDATE/DELETE nas tabelas de versão.
Finalidade: saber quanto cada pessoa deve ao próprio usuário (minimização: sem CPF, contato ou
qualquer outro dado do terceiro).

Pontos registrados na revisão da API (2026-11-12):

1. **Retenção:** o nome do terceiro fica em todas as versões da linha de `pessoa` e também na linha
   marcada como excluída (a exclusão é lógica e copia o nome). Não há anonimização na v1. Um pedido
   de eliminação do titular (LGPD art. 18) seria atendido por rotina administrativa fora da
   aplicação, com função de banco dedicada para sobrescrever o nome em todas as versões. Essa
   função **ainda não existe** e é pendência explícita (a criar antes de qualquer uso por terceiros
   ou se o usuário a pedir).
2. **`descricao` é texto livre** (ADR 030) e pode conter o nome de um terceiro. Por isso o pipeline
   (SPEC-014) **não pode levar `descricao` ao DuckDB**, nem de lançamento nem de fatura; o analítico
   recebe só agregados e ids. A SPEC-014 deve ter um teste que garanta isso.
3. **Log do Postgres:** o nome de terceiro chega ao banco como parâmetro de `pessoa_gravar`. O
   `docker-compose.yml` e os scripts de `db/docker/initdb` não definem `log_statement`,
   `log_parameter_max_length*` nem `command:` com opções de log, então valem os padrões da imagem
   `postgres:17.6` (`log_statement=none`, parâmetros não registrados, `log_min_duration_statement`
   desligado). Isso não foi conferido numa instância em execução. Não ligar `log_statement=all`,
   `log_min_duration_statement` baixo nem `log_parameter_max_length*` no contêiner sem rever este
   ADR; alterar o compose exige aviso ao usuário.
4. **API:** o 422 de validação não ecoa o valor recebido (o nome não volta no erro) e corpo com
   chave desconhecida em lançamento é recusado (INV-32), em vez de ignorado.

## Revisão

Revisar se terceiros passarem a ter acesso ao sistema, se a divisão de compra for pedida, ou quando
os bancos reais mostrarem como tratam estorno de compra de terceiro.
