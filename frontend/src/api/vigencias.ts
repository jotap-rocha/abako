// Parâmetros com vigência ("vale a partir de uma data"): fechamento e vencimento do cartão,
// meta da reserva e horizonte do R2. Repetir a mesma gravação é seguro (idempotente no servidor).

import { type Leitura, ler } from "./base";
import { type Escrita, escrever } from "./escrita";
import {
  type FechamentoSaida,
  type HorizonteSaida,
  type ParametroSaida,
  type VencimentoSaida,
  cartoesListarFechamentos,
  cartoesRegistrarFechamento,
  r2GravarHorizonte,
  r2ListarHorizontes,
  reservaGravarParametros,
  reservaListarParametros,
  vencimentosGravarVencimento,
  vencimentosListarVencimentos,
} from "./gerado";

export const listarFechamentos = (contaId: number): Promise<Leitura<FechamentoSaida[]>> =>
  ler(() => cartoesListarFechamentos({ path: { conta_id: contaId } }));

export const gravarFechamento = (
  contaId: number,
  dia: number,
  vigenteDesde: string,
): Promise<Escrita<FechamentoSaida>> =>
  escrever(() =>
    cartoesRegistrarFechamento({
      path: { conta_id: contaId },
      body: { dia, vigente_desde: vigenteDesde },
    }),
  );

export const listarVencimentos = (contaId: number): Promise<Leitura<VencimentoSaida[]>> =>
  ler(() => vencimentosListarVencimentos({ path: { conta_id: contaId } }));

export const gravarVencimento = (
  contaId: number,
  dia: number,
  vigenteDesde: string,
): Promise<Escrita<VencimentoSaida>> =>
  escrever(() =>
    vencimentosGravarVencimento({
      path: { conta_id: contaId },
      body: { dia, vigente_desde: vigenteDesde },
    }),
  );

export const listarParametrosReserva = (): Promise<Leitura<ParametroSaida[]>> =>
  ler(() => reservaListarParametros());

export type DadosReserva = {
  meses: number;
  gastoEssencial: string;
  dataAlvo: string | null;
  vigenteDesde: string;
};

export const gravarParametrosReserva = (d: DadosReserva): Promise<Escrita<ParametroSaida>> =>
  escrever(() =>
    reservaGravarParametros({
      body: {
        meses: d.meses,
        gasto_essencial: d.gastoEssencial,
        data_alvo: d.dataAlvo,
        vigente_desde: d.vigenteDesde,
      },
    }),
  );

export const listarHorizontes = (): Promise<Leitura<HorizonteSaida[]>> =>
  ler(() => r2ListarHorizontes());

export const gravarHorizonte = (
  dias: number,
  vigenteDesde: string,
): Promise<Escrita<HorizonteSaida>> =>
  escrever(() => r2GravarHorizonte({ body: { dias, vigente_desde: vigenteDesde } }));
