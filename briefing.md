Agente fin-frontend:

React + TypeScript, SPA instalável (PWA), consumindo a API FastAPI por cliente gerado do OpenAPI. Dinheiro sempre como texto ou decimal, nunca float. Formulário dinâmico dirigido pela matriz tipo→campos (7 tipos: débito/pix, crédito, receita, transferência, investimento, repasse, rendimento), categorias dependentes do tipo, grupo dentro da categoria, estabelecimento com autocomplete. Telas do MVP: saldos por conta, cartão (fatura aberta/fechada e limite usado da linha), cobertura da reserva em meses, lançamento manual, edição com histórico, conferência por snapshot com divergência. Nenhuma regra de cálculo financeiro no front. Alvo: Chrome no desktop; v1 só PC, layout responsivo. O usuário não domina web: explicar termos.

KB react-pwa:

Manifest, service worker, instalação no Android Chrome e limites do iOS, sem escrita offline no MVP, padrões de formulário com validação, testes de componente e de ponta a ponta, tratamento de decimal no JavaScript (texto ou biblioteca, nunca número).

KB postgres-financeiro (se a sua sql-patterns for genérica):

NUMERIC com escala definida no SPEC, constraints para as invariantes do ledger, SCD 2 por vigência (válido de/até) e exclusão lógica, transferência em duas pontas com soma zero, views SQL para saldo derivado, fatura e limite, datas com timestamptz e data civil em America/Sao_Paulo.

KB seguranca-local:

DEC-009 e DEC-013: localhost apenas, .env e gitleaks, backup com age, confirmação de comandos destrutivos, revisão de skills de terceiros, pacote do revisor sem dado real.