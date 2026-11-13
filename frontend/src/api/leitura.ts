// Leituras das telas de cartão, gasto real, reserva, sobra do R2 e alertas, pelo cliente gerado.
// Todas devolvem um resultado tipado em vez de lançar (a tela trata carregando, erro, vazio e
// sucesso). Os valores seguem texto, como a API devolve: o front não soma, não compara e não
// recalcula nada (ADR 015). Nada daqui vai para log, URL ou cache (ADR 040).

import {
  type AlertasSaida,
  type ContaSaida,
  type FaturaSaida,
  type GastoRealSaida,
  type LimiteSaida,
  type PessoaSaida,
  type ReceitaSaida,
  type RecorrenteSaida,
  type SituacaoR2Saida,
  type SituacaoSaida,
  alertasListar,
  cartoesFatura,
  contasListar,
  gastoRealGastoReal,
  gastoRealReceita,
  linhasCreditoLimite,
  pessoasListar,
  r2Situacao,
  recorrentesListar,
  reservaSituacao,
} from "./gerado";

export type Leitura<T> =
  | { tipo: "ok"; dados: T }
  | { tipo: "sessao_expirada" }
  // 422: o servidor recusou o pedido (ex.: mês fora do formato).
  | { tipo: "invalido" }
  // 404: a coisa pedida não existe (ex.: cartão de outro usuário).
  | { tipo: "nao_encontrado" }
  | { tipo: "erro" };

type Resposta<T> = { data?: T; response?: Response };

/** Traduz o status HTTP no resultado tipado; qualquer falha de rede vira "erro". */
async function ler<T>(chamada: () => Promise<Resposta<T>>): Promise<Leitura<T>> {
  try {
    const resposta = await chamada();
    const status = resposta.response?.status;
    if (status === 200 && resposta.data !== undefined) {
      return { tipo: "ok", dados: resposta.data };
    }
    if (status === 401) return { tipo: "sessao_expirada" };
    if (status === 404) return { tipo: "nao_encontrado" };
    if (status === 422) return { tipo: "invalido" };
    return { tipo: "erro" };
  } catch {
    return { tipo: "erro" };
  }
}

export const listarContas = (): Promise<Leitura<ContaSaida[]>> => ler(() => contasListar());

export const listarPessoas = (): Promise<Leitura<PessoaSaida[]>> => ler(() => pessoasListar());

export const listarRecorrentes = (): Promise<Leitura<RecorrenteSaida[]>> =>
  ler(() => recorrentesListar());

/** `competencia` é "AAAA-MM", o mês do fechamento da fatura. */
export const obterFatura = (contaId: number, competencia: string): Promise<Leitura<FaturaSaida>> =>
  ler(() => cartoesFatura({ path: { conta_id: contaId, competencia } }));

export const obterLimite = (linhaId: number): Promise<Leitura<LimiteSaida>> =>
  ler(() => linhasCreditoLimite({ path: { linha_id: linhaId } }));

/** `mes` é "AAAA-MM"; sem ele a API usa o mês corrente de São Paulo. */
export const obterGastoReal = (mes: string): Promise<Leitura<GastoRealSaida>> =>
  ler(() => gastoRealGastoReal({ query: { mes } }));

export const obterReceita = (mes: string): Promise<Leitura<ReceitaSaida>> =>
  ler(() => gastoRealReceita({ query: { mes } }));

export const obterReserva = (): Promise<Leitura<SituacaoSaida>> => ler(() => reservaSituacao());

export const obterR2 = (): Promise<Leitura<SituacaoR2Saida>> => ler(() => r2Situacao());

export const obterAlertas = (): Promise<Leitura<AlertasSaida>> => ler(() => alertasListar());
