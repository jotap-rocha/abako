// Como cada tipo de conta aparece na tela (ADR 042). Só texto: quem aplica as regras de cada
// tipo é o servidor.

import type { TipoConta } from "../api/contas";

export const TIPOS_CONTA: { valor: TipoConta; rotulo: string; ajuda: string }[] = [
  { valor: "corrente", rotulo: "Conta corrente", ajuda: "Onde o dinheiro do dia a dia fica." },
  {
    valor: "reserva",
    rotulo: "Reserva (caixinha, cofre)",
    ajuda: "Dinheiro guardado, com saldo separado da conta corrente. Pode pertencer a um banco.",
  },
  {
    valor: "investimento",
    rotulo: "Investimento",
    ajuda: "Aplicação fora da reserva, como corretora. Pode pertencer a um banco.",
  },
  {
    valor: "beneficio",
    rotulo: "Benefício (vale)",
    ajuda: "Vale-refeição ou alimentação. O que sai dela não conta no gasto real.",
  },
];

/** Etiqueta curta ao lado do nome; conta corrente não precisa de etiqueta. */
export const ETIQUETA: Record<TipoConta, string | null> = {
  corrente: null,
  reserva: "Reserva",
  investimento: "Investimento",
  beneficio: "Benefício",
};

/** Só reserva e investimento pertencem a uma conta corrente do mesmo banco. */
export function podeTerBanco(tipo: TipoConta): boolean {
  return tipo === "reserva" || tipo === "investimento";
}
