// Dinheiro chega da API como texto decimal ("1234.56") e fica texto no front (ADR 015, INV-14).
// Aqui só se muda a apresentação ("R$ 1.234,56"): nenhuma conta, nenhum `number`, nenhum
// arredondamento. Valor fora do formato esperado volta como veio, para o erro aparecer.

const DECIMAL_DUAS_CASAS = /^(-?)(\d+)\.(\d{2})$/;

export function formatarMoeda(valor: string): string {
  const partes = DECIMAL_DUAS_CASAS.exec(valor);
  if (partes === null) {
    return valor;
  }
  const [, sinal, inteiro, centavos] = partes;
  const comMilhar = (inteiro ?? "").replace(/\B(?=(\d{3})+(?!\d))/g, ".");
  return `${sinal}R$ ${comMilhar},${centavos}`;
}

// O que a API aceita como valor (mesmo padrão de `PADRAO_VALOR` no backend).
const VALOR_DA_API = /^-?\d{1,12}(\.\d{1,2})?$/;
const COM_VIRGULA = /^(\d{1,3}(\.\d{3})*|\d+),\d{1,2}$/;
const PONTO_DECIMAL = /^\d+(\.\d{1,2})?$/;
const SO_MILHAR = /^\d{1,3}(\.\d{3})+$/;

/**
 * Traduz o valor digitado no jeito brasileiro ("1.234,56", "R$ 50", "-10,5") para o texto que a
 * API espera ("1234.56"). Só troca caracteres: nenhuma conta, nenhum `number`. Devolve `null`
 * quando o texto não é um valor reconhecível, para a tela pedir a correção.
 *
 * Com vírgula, ela é a decimal e os pontos são de milhar. Sem vírgula, "1.234" é milhar e
 * "12.5" é decimal (um ponto seguido de 1 ou 2 dígitos).
 */
export function lerValorDigitado(digitado: string): string | null {
  const limpo = digitado.replace(/R\$/g, "").replace(/\s/g, "");
  const negativo = limpo.startsWith("-");
  const corpo = negativo ? limpo.slice(1) : limpo;
  let normalizado: string | null = null;
  if (COM_VIRGULA.test(corpo)) {
    normalizado = corpo.replace(/\./g, "").replace(",", ".");
  } else if (PONTO_DECIMAL.test(corpo)) {
    normalizado = corpo;
  } else if (SO_MILHAR.test(corpo)) {
    normalizado = corpo.replace(/\./g, "");
  }
  if (normalizado === null) return null;
  const resultado = `${negativo ? "-" : ""}${normalizado}`;
  return VALOR_DA_API.test(resultado) ? resultado : null;
}

/**
 * Decimal que não é dinheiro (ex.: cobertura "9.99" meses) no jeito brasileiro ("9,99"). Só troca
 * o ponto pela vírgula no texto: nenhuma conta, nenhum `number`. Fora do formato, volta como veio.
 */
export function formatarDecimal(valor: string): string {
  return /^-?\d+(\.\d+)?$/.test(valor) ? valor.replace(".", ",") : valor;
}
