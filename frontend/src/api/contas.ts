// Leitura de contas pelo cliente gerado. Devolve um resultado tipado em vez de lançar, para a
// tela tratar sempre os quatro estados: carregando, sucesso, vazio (lista vazia) e erro.

import { type ContaSaida, contasListar } from "./gerado";

export type ResultadoContas =
  | { tipo: "ok"; contas: ContaSaida[] }
  | { tipo: "sessao_expirada" }
  | { tipo: "erro" };

export async function listarContas(): Promise<ResultadoContas> {
  try {
    const resposta = await contasListar();
    const status = resposta.response?.status;
    if (status === 200 && resposta.data !== undefined) {
      return { tipo: "ok", contas: resposta.data };
    }
    return status === 401 ? { tipo: "sessao_expirada" } : { tipo: "erro" };
  } catch {
    return { tipo: "erro" };
  }
}
