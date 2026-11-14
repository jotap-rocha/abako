// Recorrentes, ocorrências do mês e vínculo com transação, pelo cliente gerado (ADR 048).

import { type Leitura, ler } from "./base";
import { type Escrita, apagar, escrever } from "./escrita";
import {
  type OcorrenciaSaida,
  type RecorrenteEntrada,
  type RecorrenteSaida,
  recorrentesCriar,
  recorrentesDesvincular,
  recorrentesEditar,
  recorrentesExcluir,
  recorrentesOcorrencias,
  recorrentesVincular,
} from "./gerado";

export type DadosRecorrente = RecorrenteEntrada;

/** `mes` é "AAAA-MM". */
export const listarOcorrencias = (mes: string): Promise<Leitura<OcorrenciaSaida[]>> =>
  ler(() => recorrentesOcorrencias({ query: { mes } }));

export const criarRecorrente = (dados: DadosRecorrente): Promise<Escrita<RecorrenteSaida>> =>
  escrever(() => recorrentesCriar({ body: dados }));

/** `versao` é a que a tela leu; se outra edição veio antes, volta "desatualizado". */
export const editarRecorrente = (
  recorrenteId: number,
  versao: number,
  dados: DadosRecorrente,
): Promise<Escrita<RecorrenteSaida>> =>
  escrever(() =>
    recorrentesEditar({ path: { recorrente_id: recorrenteId }, body: { ...dados, versao } }),
  );

export const excluirRecorrente = (recorrenteId: number, versao: number): Promise<Escrita<null>> =>
  apagar(() => recorrentesExcluir({ path: { recorrente_id: recorrenteId }, query: { versao } }));

export const vincularOcorrencia = (
  recorrenteId: number,
  mes: string,
  transacaoId: number,
): Promise<Escrita<OcorrenciaSaida>> =>
  escrever(() =>
    recorrentesVincular({
      path: { recorrente_id: recorrenteId, mes },
      body: { transacao_id: transacaoId },
    }),
  );

export const desvincularOcorrencia = (
  recorrenteId: number,
  mes: string,
): Promise<Escrita<OcorrenciaSaida>> =>
  escrever(() => recorrentesDesvincular({ path: { recorrente_id: recorrenteId, mes } }));
