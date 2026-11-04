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
