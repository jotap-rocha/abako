// Lançamentos pelo cliente gerado. Como em `contas.ts`, devolve um resultado tipado em vez de
// lançar. Os valores são texto no formato da API ("1234.56", sempre positivo; o tipo dá o sinal).
// Escritas nunca são repetidas aqui: quem decide tentar de novo é o usuário, com a mesma chave.

import {
  type LancamentoEntrada,
  type LancamentoSaida,
  lancamentosCriar,
  lancamentosEditar,
  lancamentosExcluir,
  lancamentosListar,
} from "./gerado";

export type TipoLancamento = LancamentoEntrada["tipo"];

/** O que o formulário preenche; a chave só existe ao criar, a versão só ao editar. */
export type DadosLancamento = Omit<LancamentoEntrada, "chave">;

export type ResultadoListar =
  | { tipo: "ok"; lancamentos: LancamentoSaida[] }
  | { tipo: "sessao_expirada" }
  | { tipo: "erro" };

export type ResultadoGravar =
  | { tipo: "ok"; lancamento: LancamentoSaida; repetido: boolean }
  | { tipo: "sessao_expirada" }
  | { tipo: "desatualizado" }
  | { tipo: "nao_encontrado" }
  | { tipo: "excluido" }
  | { tipo: "invalido"; mensagem: string | null }
  | { tipo: "erro" };

export type ResultadoExcluir =
  | { tipo: "ok" }
  | { tipo: "sessao_expirada" }
  | { tipo: "desatualizado" }
  | { tipo: "nao_encontrado" }
  | { tipo: "erro" };

/** A mensagem de regra que o servidor devolve em `detail` (texto curto, sem dado financeiro). */
function mensagemDoServidor(erro: unknown): string | null {
  if (typeof erro === "object" && erro !== null && "detail" in erro) {
    const detalhe = (erro as { detail: unknown }).detail;
    if (typeof detalhe === "string") return detalhe;
  }
  return null;
}

export async function listarLancamentos(): Promise<ResultadoListar> {
  try {
    const resposta = await lancamentosListar();
    const status = resposta.response?.status;
    if (status === 200 && resposta.data !== undefined) {
      return { tipo: "ok", lancamentos: resposta.data };
    }
    return status === 401 ? { tipo: "sessao_expirada" } : { tipo: "erro" };
  } catch {
    return { tipo: "erro" };
  }
}

/** `chave` é a do formulário: repetir a mesma devolve o lançamento original (`repetido`). */
export async function criarLancamento(
  chave: string,
  dados: DadosLancamento,
): Promise<ResultadoGravar> {
  try {
    const resposta = await lancamentosCriar({ body: { ...dados, chave } });
    const status = resposta.response?.status;
    if ((status === 201 || status === 200) && resposta.data !== undefined) {
      return { tipo: "ok", lancamento: resposta.data, repetido: status === 200 };
    }
    if (status === 401) return { tipo: "sessao_expirada" };
    if (status === 409) return { tipo: "excluido" };
    if (status === 422) return { tipo: "invalido", mensagem: mensagemDoServidor(resposta.error) };
    return { tipo: "erro" };
  } catch {
    return { tipo: "erro" };
  }
}

/** `versao` é a que a tela leu; se outra edição veio antes, volta "desatualizado". */
export async function editarLancamento(
  transacaoId: number,
  versao: number,
  dados: DadosLancamento,
): Promise<ResultadoGravar> {
  try {
    const resposta = await lancamentosEditar({
      path: { transacao_id: transacaoId },
      body: { ...dados, versao },
    });
    const status = resposta.response?.status;
    if (status === 200 && resposta.data !== undefined) {
      return { tipo: "ok", lancamento: resposta.data, repetido: false };
    }
    if (status === 401) return { tipo: "sessao_expirada" };
    if (status === 404) return { tipo: "nao_encontrado" };
    if (status === 409) return { tipo: "desatualizado" };
    if (status === 422) return { tipo: "invalido", mensagem: mensagemDoServidor(resposta.error) };
    return { tipo: "erro" };
  } catch {
    return { tipo: "erro" };
  }
}

export async function excluirLancamento(
  transacaoId: number,
  versao: number,
): Promise<ResultadoExcluir> {
  try {
    const resposta = await lancamentosExcluir({
      path: { transacao_id: transacaoId },
      query: { versao },
    });
    const status = resposta.response?.status;
    if (status === 204) return { tipo: "ok" };
    if (status === 401) return { tipo: "sessao_expirada" };
    if (status === 404) return { tipo: "nao_encontrado" };
    if (status === 409) return { tipo: "desatualizado" };
    return { tipo: "erro" };
  } catch {
    return { tipo: "erro" };
  }
}
