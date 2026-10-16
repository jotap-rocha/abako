# Rubrica para o revisor adversarial

Você audita uma entrega de software financeiro pessoal. Seja cético: assuma que há erros e tente prová-los. Não aceite afirmações sem evidência no código ou nos testes. Se não puder verificar algo, diga "não verificável" em vez de supor.

## Como proceder
1. Para **cada exemplo numérico** (fixtures e critérios), recalcule passo a passo, sem confiar no resultado informado.
2. Para cada item abaixo, responda: **OK / FALHA / NÃO VERIFICÁVEL**, com arquivo e linha como evidência.
3. Liste achados por severidade (crítico, alto, médio, baixo), cada um com: o que, onde, cenário que quebra, correção sugerida.
4. Não reescreva o sistema; aponte e justifique.

## A. Dinheiro e cálculo
- A1. Nenhum valor monetário usa float/double em código, SQL ou JSON (valores como texto).
- A2. Arredondamento de parcelas: soma = total; a última absorve os centavos.
- A3. Saldo derivado = último snapshot + transações válidas posteriores; divergência é sinalizada e nunca corrigida sozinha.
- A4. Gasto real exclui transferência, investimento, repasse, rendimento, pagamento de fatura, despesas de terceiros e de conta de benefício.
- A5. Limite usado considera o valor total das compras (parcelas futuras e terceiros).
- A6. Estorno: integral vs. com parcelas pagas; líquido da compra zero; nenhum dinheiro vai à conta corrente.
- A7. Níveis da reserva mudam exatamente nos cortes de 50% e 100%.
- A8. Sobra do R2 usa só fatura própria, ocorrências não vinculadas dentro do horizonte; crédito do vale não entra no disponível.
- A9. Vale: sobra = Σ max(resta, 0); estouro não é compensado; decisão não move saldo.
- A10. Datas são datas civis em America/Sao_Paulo; bordas de virada de mês/dia testadas.

## B. Integridade e histórico
- B1. Edição cria versão; só a vigente conta; histórico preservado; exclusão lógica.
- B2. Papel da aplicação não tem UPDATE/DELETE nas tabelas de versão do ledger.
- B3. Pipeline lê o transacional e escreve só no analítico; analítico só tem agregados.

## C. Segurança
- C1. Toda consulta é filtrada por `user_id` vindo da sessão (nunca do corpo da requisição).
- C2. Senhas com Argon2id; nunca em log; sessão no servidor; cookie HttpOnly + SameSite.
- C3. CSRF (Origin + token), CORS restrito, validação de Host, rate limit de login.
- C4. Nenhum segredo, dado real, `.env`, dump ou backup no repositório ou no pacote.
- C5. Nenhuma credencial bancária armazenada ou solicitada.
- C6. Serviços escutam só em localhost.

## D. Testes
- D1. Cada invariante em `tests/contracts/invariantes.yaml` tem teste; cada critério em `criterios.yaml` também.
- D2. Testes de regra financeira usam as fixtures e conferem os valores esperados (não tautologias).
- D3. A suíte aborta se a conexão de banco não for a de teste.
- D4. Existem testes baseados em propriedades (Hypothesis) para as invariantes numéricas.
- D5. O comando `check` está verde; não há testes ignorados sem justificativa.

## E. CI/CD
- E1. Ações fixadas por SHA; permissões mínimas; sem `pull_request_target`; sem segredos; sem self-hosted runner.
- E2. Deploy local recusa sem backup recente.

## Formato da resposta
Tabela: item | OK/FALHA/NÃO VERIFICÁVEL | evidência | observação. Depois, lista de achados por severidade.
