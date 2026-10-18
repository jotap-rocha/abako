---
domain: react-pwa
topic: formularios
confidence: null
mcp_validated: null
---

# abako — formulários React (ADR 011, 015)

- **Matriz tipo → campos** como dado (`frontend/src/dominio/matriz-tipos.ts`), não `if` espalhado. 7 tipos: débito/pix, crédito, receita, transferência, investimento, repasse, rendimento.
- Biblioteca sugerida: React Hook Form + Zod (`zodResolver`); schema Zod **por tipo** (união discriminada).
- Dinheiro: campo de texto com máscara; valor no estado como **string** decimal (`"1234.50"`); nunca `parseFloat`/`number`. Validar com regex `^\d+(\.\d{1,2})?$` e enviar string.
- Categoria depende do tipo; grupo dentro da categoria; estabelecimento com autocomplete (debounce, lista vinda da API).
- Transferência cria **duas pernas** no backend; o formulário só coleta origem/destino/valor.
- Crédito: parcelas e cartão; a divisão em parcelas é **calculada pelo backend**, o front só exibe.
- Vale: bolso obrigatório (padrão pessoal).
- Estados: carregando, erro de validação por campo, erro de API, sucesso. Teste RTL por tipo + 1 jornada Playwright.

> Texto escrito a partir dos ADRs do projeto. Versões e flags de ferramentas externas devem ser conferidas na documentação atual (context7) ao implementar; não foram validadas aqui.
