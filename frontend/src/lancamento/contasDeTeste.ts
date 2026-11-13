// Contas sintéticas usadas pelos testes da tela de lançamento.
import type { SaldoSaida } from "../api/gerado";

function conta(parcial: Partial<SaldoSaida> & Pick<SaldoSaida, "conta_id" | "nome">): SaldoSaida {
  return {
    conta_beneficio: false,
    tipo: "corrente",
    conta_mae_id: null,
    saldo: "0.00",
    snapshot_data: null,
    snapshot_valor: null,
    ...parcial,
  };
}

export const CONTAS: SaldoSaida[] = [
  conta({ conta_id: 1, nome: "Banco A" }),
  conta({ conta_id: 2, nome: "Corretora", tipo: "investimento" }),
  conta({ conta_id: 3, nome: "Vale", tipo: "beneficio", conta_beneficio: true }),
  conta({ conta_id: 4, nome: "Cartão A", tipo: "divida" }),
];
