// Respostas sintéticas da API do vale para os testes. Nada aqui é dado real. Os números NÃO são
// coerentes entre si de propósito (resta, sobra e saldo inventados): se a tela recalculasse algo,
// o texto mudaria.
import type {
  AlertaSaida,
  BeneficiosSaida,
  ContaSaida,
  DecisaoHistoricoSaida,
  SituacaoValeSaida,
} from "../api/gerado";

export const CONTA_VR: ContaSaida = {
  conta_id: 31,
  nome: "Vale A",
  tipo: "beneficio",
  conta_beneficio: true,
  conta_mae_id: null,
  linha_credito_id: null,
  versao: 1,
};

export const CONTA_VA: ContaSaida = { ...CONTA_VR, conta_id: 32, nome: "Vale B" };

export const SITUACAO_OK: SituacaoValeSaida = {
  mes: "2026-11",
  mes_encerrado: false,
  estado: "ok",
  conta_vr_id: 31,
  credito: "1111.11",
  base_trabalho: "222.22",
  trabalho: {
    inicial: "333.33",
    ajuste: "44.44",
    alocacao: "555.55",
    consumo: "666.66",
    resta: "-777.77",
  },
  pessoal: {
    inicial: "888.88",
    ajuste: "0.00",
    alocacao: "999.99",
    consumo: "12.34",
    resta: "432.10",
  },
  sobra: "111.00",
  decisao_destino: null,
  decisao_versao: null,
  destino_padrao: "pessoal",
  saldo_total: "2468.13",
  receita_caixa: "3000.01",
  receita_beneficio: "1500.02",
  receita_total: "9999.99",
};

export const SITUACAO_SEM_CONTA: SituacaoValeSaida = {
  ...SITUACAO_OK,
  estado: "sem_conta",
  conta_vr_id: null,
  base_trabalho: null,
  saldo_total: null,
  credito: "0.00",
};

export const SITUACAO_SEM_CREDITO: SituacaoValeSaida = {
  ...SITUACAO_OK,
  estado: "sem_credito",
  credito: "0.00",
};

export const BENEFICIOS: BeneficiosSaida = {
  mes: "2026-11",
  itens: [
    {
      conta_id: 31,
      vale_refeicao: true,
      receita_mes: "1000.00",
      despesa_mes: "300.00",
      saldo_total: "4444.44",
    },
    {
      conta_id: 32,
      vale_refeicao: false,
      receita_mes: "500.00",
      despesa_mes: "50.00",
      saldo_total: "5555.55",
    },
  ],
};

export const DECISOES: DecisaoHistoricoSaida[] = [
  { mes: "2026-10-01", destino: "trabalho", versao: 1, vigente: false },
  { mes: "2026-10-01", destino: "nenhum", versao: 2, vigente: true },
];

export const ALERTA_R5: AlertaSaida = {
  codigo: "R5",
  tipo: "alerta",
  severidade: "alta",
  detalhe: "vale_trabalho_estourado",
  mensagem: "O bolso de trabalho do vale estourou.",
  reserva: null,
  r2: null,
  r4: null,
  vale: {
    conta_id: 31,
    bolso: "trabalho",
    mes: "2026-11-01",
    alocacao: "100.00",
    consumo: "130.00",
    resta: "-30.00",
  },
};
