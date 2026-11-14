// Respostas sintéticas da API para os testes das telas de leitura. Nada aqui é dado real.
import type {
  AlertaSaida,
  ContaSaida,
  FaturaSaida,
  GastoRealSaida,
  LimiteSaida,
  PessoaSaida,
  ReceitaSaida,
  SituacaoR2Saida,
  SituacaoSaida,
} from "../api/gerado";

export const CARTAO: ContaSaida = {
  conta_id: 7,
  nome: "Cartão azul",
  tipo: "divida",
  conta_beneficio: false,
  conta_mae_id: null,
  linha_credito_id: 3,
  versao: 1,
};

export const CORRENTE: ContaSaida = {
  conta_id: 1,
  nome: "Conta principal",
  tipo: "corrente",
  conta_beneficio: false,
  conta_mae_id: null,
  linha_credito_id: null,
  versao: 1,
};

export const PESSOAS: PessoaSaida[] = [{ pessoa_id: 5, nome: "Maria Teste", versao: 1 }];

// Total, própria e terceiros de propósito NÃO batem com os itens: a tela tem de mostrar o que
// veio, sem somar nada.
export const FATURA: FaturaSaida = {
  competencia: "2026-11",
  fechamento: "2026-11-10",
  situacao: "aberta",
  total: "999.00",
  propria: "111.11",
  terceiros: "222.22",
  itens: [
    {
      transacao_id: 1,
      versao: 1,
      parcela: 2,
      parcelas: 3,
      data_compra: "2026-10-05",
      valor: "10.00",
      descricao: "Geladeira",
      pessoa_id: null,
    },
    {
      transacao_id: 2,
      versao: 1,
      parcela: 1,
      parcelas: 1,
      data_compra: "2026-10-20",
      valor: "20.00",
      descricao: "Presente",
      pessoa_id: 5,
    },
    {
      transacao_id: 3,
      versao: 1,
      parcela: 1,
      parcelas: 1,
      data_compra: "2026-10-21",
      valor: "-15.50",
      descricao: "Estorno da blusa",
      pessoa_id: null,
    },
  ],
};

export const LIMITE: LimiteSaida = { limite: "5000.00", usado: "5250.00", disponivel: "-250.00" };

export const GASTO: GastoRealSaida = {
  mes: "2026-11",
  total: "7777.77",
  por_conta: [
    { conta_id: 1, valor: "100.00" },
    { conta_id: 7, valor: "50.00" },
  ],
};

export const RECEITA: ReceitaSaida = {
  mes: "2026-11",
  caixa: "4321.09",
  beneficio: "600.00",
  total: "4921.09",
};

// Nível "critica" com falta zero e cobertura enorme não fazem sentido juntos: é de propósito, para
// provar que a tela não recalcula o nível a partir dos números.
export const RESERVA: SituacaoSaida = {
  alvo_vencida: false,
  aporte_mensal: "321.00",
  cobertura_meses: "9.99",
  config_pendente: false,
  contas_reserva: 1,
  data_alvo: "2027-06-30",
  falta: "0.00",
  gasto_essencial: "2000.00",
  imposto_acumulado: "12.34",
  meses_ate_alvo: 7,
  meses_meta: 3,
  meta: "6000.00",
  nivel: "critica",
  saldo_bruto: "70000.00",
  saldo_liquido: "69987.66",
};

export const RESERVA_SEM_CONFIG: SituacaoSaida = {
  ...RESERVA,
  config_pendente: true,
  nivel: null,
  falta: null,
  cobertura_meses: null,
  meta: null,
  gasto_essencial: null,
  aporte_mensal: null,
  data_alvo: null,
  meses_ate_alvo: null,
};

export const R2: SituacaoR2Saida = {
  alerta: true,
  compromissos: "1.00",
  data_fim: "2026-11-22",
  disponivel: "2.00",
  faturas_proprias: "0.00",
  fixos_pendentes: "0.00",
  horizonte_dias: 10,
  itens: [
    {
      grupo: "fixo",
      recorrente_id: 9,
      conta_id: 1,
      data: "2026-11-15",
      valor: "800.00",
      bruto: null,
      pago: null,
      parcial: null,
      competencia: null,
      tipo: "fixo",
    },
    {
      grupo: "fatura",
      recorrente_id: null,
      conta_id: 7,
      data: "2026-11-20",
      valor: "300.00",
      bruto: "450.00",
      pago: "150.00",
      parcial: true,
      competencia: "2026-11",
      tipo: null,
    },
    {
      grupo: "vencida",
      recorrente_id: 10,
      conta_id: 1,
      data: "2026-11-01",
      valor: "55.00",
      bruto: null,
      pago: null,
      parcial: null,
      competencia: null,
      tipo: "fixo",
    },
  ],
  pendencias_vencimento: 0,
  receitas_pendentes: "0.00",
  saldos_correntes: "0.00",
  sobra: "-8888.88",
  vencidas: 1,
};

export const RECORRENTES = [
  {
    recorrente_id: 9,
    nome: "Aluguel",
    tipo: "fixo",
    valor: "800.00",
    dia: 15,
    conta_id: 1,
    mes_inicio: "2026-01",
    mes_fim: null,
    versao: 1,
  },
  {
    recorrente_id: 10,
    nome: "Internet",
    tipo: "fixo",
    valor: "55.00",
    dia: 1,
    conta_id: 1,
    mes_inicio: "2026-01",
    mes_fim: null,
    versao: 1,
  },
];

// Ordem de propósito: "baixa" antes de "alta". A tela mantém a ordem da API.
export const ALERTAS: AlertaSaida[] = [
  {
    codigo: "CONFIG",
    tipo: "configuracao",
    severidade: "baixa",
    detalhe: "reserva_gasto_essencial",
    mensagem: "Informe o gasto essencial para calcular a meta da reserva.",
    reserva: null,
    r2: null,
    r4: null,
    vale: null,
  },
  {
    codigo: "R4",
    tipo: "aviso",
    severidade: "alta",
    detalhe: "divergencia_saldo",
    mensagem: "O saldo informado não bate com o calculado.",
    reserva: null,
    r2: null,
    r4: {
      conta_id: 1,
      data_snapshot: "2026-11-03",
      valor_snapshot: "900.00",
      saldo_derivado: "950.00",
      divergencia: "50.00",
      quantidade: 2,
    },
    vale: null,
  },
];
