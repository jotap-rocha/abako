// Matriz tipo → campos do formulário de lançamento (ADR 011) e quais contas cada tipo aceita.
// Só apresentação: quem aplica as regras de cada tipo é o servidor, que recusa o que não vale.

import type { TipoLancamento } from "../api/lancamentos";
import type { SaldoSaida } from "../api/gerado";

export type InfoTipo = {
  valor: TipoLancamento;
  rotulo: string;
  ajuda: string;
  /** Compra no cartão: número de parcelas (o valor digitado é o total da compra). */
  pedeParcelas: boolean;
  /** Pessoa (terceiro): opcional na compra a crédito (sem pessoa = compra própria), obrigatória no repasse. */
  pessoa: "opcional" | "obrigatoria" | null;
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
    pedeParcelas: false,
    pessoa: null,
    pedeBrutoEImposto: false,
    pedeDestino: false,
    rotuloConta: "Conta de onde saiu",
  },
  {
    valor: "receita",
    rotulo: "Receita",
    ajuda: "Dinheiro que entra na conta: salário, venda, reembolso.",
    pedeParcelas: false,
    pessoa: null,
    pedeBrutoEImposto: false,
    pedeDestino: false,
    rotuloConta: "Conta que recebeu",
  },
  {
    valor: "transferencia",
    rotulo: "Transferência entre contas",
    ajuda:
      "Move dinheiro entre duas contas suas, inclusive para a caixinha ou o cofre. Não conta como gasto.",
    pedeParcelas: false,
    pessoa: null,
    pedeBrutoEImposto: false,
    pedeDestino: true,
    rotuloConta: "Conta de origem",
  },
  {
    valor: "investimento",
    rotulo: "Investimento (aplicar)",
    ajuda:
      "Dinheiro enviado a uma conta de investimento. Guardar na caixinha ou na reserva é transferência, não investimento.",
    pedeParcelas: false,
    pessoa: null,
    pedeBrutoEImposto: false,
    pedeDestino: true,
    rotuloConta: "Conta de origem",
  },
  {
    valor: "rendimento",
    rotulo: "Rendimento",
    ajuda: "Juros que a conta rendeu. Informe o valor bruto e o imposto; o abako credita a diferença.",
    pedeParcelas: false,
    pessoa: null,
    pedeBrutoEImposto: true,
    pedeDestino: false,
    rotuloConta: "Conta que rendeu",
  },
  {
    valor: "credito",
    rotulo: "Compra no cartão de crédito",
    ajuda:
      "Compra à vista ou parcelada no cartão. Ela é toda sua ou toda de uma pessoa: o abako não divide a compra.",
    pedeParcelas: true,
    pessoa: "opcional",
    pedeBrutoEImposto: false,
    pedeDestino: false,
    rotuloConta: "Cartão",
  },
  {
    valor: "repasse",
    rotulo: "Repasse recebido de terceiro",
    ajuda:
      "Dinheiro que uma pessoa devolveu e entrou na sua conta corrente. Não é receita nem gasto: só abate o que ela deve.",
    pedeParcelas: false,
    pessoa: "obrigatoria",
    pedeBrutoEImposto: false,
    pedeDestino: false,
    rotuloConta: "Conta corrente que recebeu",
  },
];

export function infoDoTipo(tipo: TipoLancamento): InfoTipo {
  return TIPOS_LANCAMENTO.find((t) => t.valor === tipo) ?? TIPOS_LANCAMENTO[0]!;
}

export function rotuloDoTipo(tipo: string): string {
  return TIPOS_LANCAMENTO.find((t) => t.valor === tipo)?.rotulo ?? tipo;
}

/**
 * Compra a crédito só em cartão (conta do tipo dívida); repasse só em conta corrente; os demais
 * tipos não usam o cartão como origem. Benefício (vale) não entra em transferência nem recebe
 * rendimento. Tudo isso o servidor recusa de qualquer jeito: aqui só se evita a escolha errada.
 */
export function contasDeOrigem(tipo: TipoLancamento, contas: SaldoSaida[]): SaldoSaida[] {
  if (tipo === "credito") return contas.filter((c) => c.tipo === "divida");
  if (tipo === "repasse") return contas.filter((c) => c.tipo === "corrente");
  const semCartao = contas.filter((c) => c.tipo !== "divida");
  const semBeneficio = tipo === "transferencia" || tipo === "rendimento";
  return semBeneficio ? semCartao.filter((c) => !c.conta_beneficio) : semCartao;
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
