// Contagens inteiras digitadas (dia do mês, número de parcelas, meses, dias de horizonte).
// Não é dinheiro. O servidor continua sendo quem decide o que vale; aqui só se evita enviar
// texto que nem é um número inteiro dentro do intervalo anunciado no campo.

/** "12" vira 12 se estiver entre `minimo` e `maximo`; qualquer outro texto devolve `null`. */
export function lerInteiro(texto: string, minimo: number, maximo: number): number | null {
  const limpo = texto.trim();
  if (!/^\d{1,4}$/.test(limpo)) return null;
  const n = +limpo;
  return n >= minimo && n <= maximo ? n : null;
}
