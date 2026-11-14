// Vale (VR) pelo cliente gerado: situação do mês, benefícios, parâmetro e decisão da sobra
// (ADR 052). Só leitura e gravação: alocação, resta, sobra e saldo são calculados pelo servidor
// (ADR 015). Nada daqui vai para log, URL (além do mês "AAAA-MM") ou armazenamento do navegador.

import { type Leitura, ler } from "./base";
import { type Escrita, escrever } from "./escrita";
import {
  type BeneficiosSaida,
  type DecisaoHistoricoSaida,
  type DecisaoValeSaida,
  type ParametroValeSaida,
  type SituacaoValeSaida,
  valeBeneficios,
  valeGravarDecisao,
  valeGravarParametro,
  valeListarDecisoes,
  valeObterParametro,
  valeSituacao,
} from "./gerado";

/** `mes` é "AAAA-MM". */
export const obterSituacaoVale = (mes: string): Promise<Leitura<SituacaoValeSaida>> =>
  ler(() => valeSituacao({ query: { mes } }));

export const obterBeneficios = (mes: string): Promise<Leitura<BeneficiosSaida>> =>
  ler(() => valeBeneficios({ query: { mes } }));

/** Parâmetro vigente no mês (padrão: o corrente); `null` se nenhuma conta é o VR. */
export const obterParametroVale = (
  mes?: string,
): Promise<Leitura<ParametroValeSaida | null>> =>
  ler(() => valeObterParametro(mes === undefined ? undefined : { query: { mes } }));

export const listarDecisoes = (mes: string): Promise<Leitura<DecisaoHistoricoSaida[]>> =>
  ler(() => valeListarDecisoes({ query: { mes } }));

export type DadosParametroVale = {
  contaId: number;
  /** Texto no formato da API ("200.00"). */
  baseTrabalho: string;
  destinoPadrao: string;
  /** Sempre o dia 1 de um mês ("AAAA-MM-01"). */
  vigenteDesde: string;
};

export const gravarParametroVale = (d: DadosParametroVale): Promise<Escrita<ParametroValeSaida>> =>
  escrever(() =>
    valeGravarParametro({
      body: {
        conta_id: d.contaId,
        base_trabalho: d.baseTrabalho,
        destino_padrao: d.destinoPadrao,
        vigente_desde: d.vigenteDesde,
      },
    }),
  );

export const gravarDecisao = (mes: string, destino: string): Promise<Escrita<DecisaoValeSaida>> =>
  escrever(() => valeGravarDecisao({ body: { mes, destino } }));
