// Matriz tipo → campos do formulário de lançamento (ADR 011) e quais contas cada tipo aceita.
// Só apresentação: quem aplica as regras de cada tipo é o servidor, que recusa o que não vale.

import type { TipoLancamento } from "../api/lancamentos";
import type { SaldoSaida } from "../api/gerado";

export type InfoTipo = {
  valor: TipoLancamento;
  rotulo: string;
  ajuda: string;
  /** Crédito e repasse chegam com as SPECs 005 e 007: aparecem, mas ainda não se pode usar. */
  emBreve: boolean;
  /** Rendimento informa bruto e imposto; os outros, um valor só. */
  pedeBrutoEImposto: boolean;
  /** Transferência e investimento levam o dinheiro de uma conta para outra. */
  pedeDestino: boolean;
  rotuloConta: string;
};

export const TIPOS_LANCAMENTO: InfoTipo[] = [
  {
    valor: "debito",
    rotulo: "Despesa (débito)",
    ajuda: "Dinheiro que sai da conta: compra no débito, Pix, boleto pago.",
    emBreve: false,
    pedeBrutoEImposto: false,
    pedeDestino: false,
    rotuloConta: "Conta de onde saiu",
  },
  {
    valor: "receita",
    rotulo: "Receita",
    ajuda: "Dinheiro que entra na conta: salário, venda, reembolso.",
    emBreve: false,
    pedeBrutoEImposto: false,
    pedeDestino: false,
    rotuloConta: "Conta que recebeu",
  },
  {
    valor: "transferencia",
    rotulo: "Transferência entre contas",
    ajuda:
      "Move dinheiro entre duas contas suas, inclusive para a caixinha ou o cofre. Não conta como gasto.",
    emBreve: false,
    pedeBrutoEImposto: false,
    pedeDestino: true,
    rotuloConta: "Conta de origem",
  },
  {
    valor: "investimento",
    rotulo: "Investimento (aplicar)",
    ajuda:
      "Dinheiro enviado a uma conta de investimento. Guardar na caixinha ou na reserva é transferência, não investimento.",
    emBreve: false,
    pedeBrutoEImposto: false,
    pedeDestino: true,
    rotuloConta: "Conta de origem",
  },
  {
    valor: "rendimento",
    rotulo: "Rendimento",
    ajuda: "Juros que a conta rendeu. Informe o valor bruto e o imposto; o abako credita a diferença.",
    emBreve: false,
    pedeBrutoEImposto: true,
    pedeDestino: false,
    rotuloConta: "Conta que rendeu",
  },
  {
    valor: "credito",
    rotulo: "Compra no cartão de crédito (em breve)",
    ajuda: "Chega junto com o cartão e as faturas.",
    emBreve: true,
    pedeBrutoEImposto: false,
    pedeDestino: false,
    rotuloConta: "Conta",
  },
  {
    valor: "repasse",
    rotulo: "Repasse a terceiros (em breve)",
    ajuda: "Chega junto com o controle de gastos de terceiros.",
    emBreve: true,
    pedeBrutoEImposto: false,
    pedeDestino: false,
    rotuloConta: "Conta",
  },
];

export function infoDoTipo(tipo: TipoLancamento): InfoTipo {
  return TIPOS_LANCAMENTO.find((t) => t.valor === tipo) ?? TIPOS_LANCAMENTO[0]!;
}

export function rotuloDoTipo(tipo: string): string {
  return TIPOS_LANCAMENTO.find((t) => t.valor === tipo)?.rotulo ?? tipo;
}

/** Benefício (vale) não entra em transferência nem recebe rendimento: o servidor recusa. */
export function contasDeOrigem(tipo: TipoLancamento, contas: SaldoSaida[]): SaldoSaida[] {
  const semBeneficio = tipo === "transferencia" || tipo === "rendimento";
  return semBeneficio ? contas.filter((c) => !c.conta_beneficio) : contas;
}

/** Transferência vai para outra conta que não seja benefício; investimento, para um investimento. */
export function contasDeDestino(
  tipo: TipoLancamento,
  contas: SaldoSaida[],
  origemId: number | null,
): SaldoSaida[] {
  if (tipo === "investimento") return contas.filter((c) => c.tipo === "investimento");
  return contas.filter((c) => !c.conta_beneficio && c.conta_id !== origemId);
}
