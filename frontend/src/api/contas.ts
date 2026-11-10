// Cadastro e edição de contas pelo cliente gerado. Devolve um resultado tipado em vez de lançar,
// para a tela mostrar uma mensagem clara em cada caso. A lista de contas vem de `listarSaldos`
// (`saldos.ts`), que já traz nome, tipo e conta do banco junto com o saldo.

import { type ContaSaida, contasCriar, contasEditar, contasObter } from "./gerado";

export type TipoConta = ContaSaida["tipo"];

export type ResultadoCriarConta =
  | { tipo: "ok"; conta: ContaSaida }
  | { tipo: "sessao_expirada" }
  | { tipo: "nome_repetido" }
  | { tipo: "invalido"; mensagem: string | null }
  | { tipo: "erro" };

export type ResultadoEditarConta =
  | ResultadoCriarConta
  | { tipo: "desatualizada" }
  | { tipo: "nao_encontrada" };

export type ResultadoObterConta =
  | { tipo: "ok"; conta: ContaSaida }
  | { tipo: "sessao_expirada" }
  | { tipo: "nao_encontrada" }
  | { tipo: "erro" };

/** A mensagem de regra que o servidor devolve em `detail` (texto curto, sem dado financeiro). */
function mensagemDoServidor(erro: unknown): string | null {
  if (typeof erro === "object" && erro !== null && "detail" in erro) {
    const detalhe = (erro as { detail: unknown }).detail;
    if (typeof detalhe === "string") return detalhe;
  }
  return null;
}

export async function criarConta(
  nome: string,
  tipo: TipoConta,
  contaMaeId: number | null,
): Promise<ResultadoCriarConta> {
  try {
    const resposta = await contasCriar({
      body: { nome, tipo, conta_beneficio: tipo === "beneficio", conta_mae_id: contaMaeId },
    });
    const status = resposta.response?.status;
    if (status === 201 && resposta.data !== undefined) {
      return { tipo: "ok", conta: resposta.data };
    }
    if (status === 401) return { tipo: "sessao_expirada" };
    if (status === 409) return { tipo: "nome_repetido" };
    if (status === 422) return { tipo: "invalido", mensagem: mensagemDoServidor(resposta.error) };
    return { tipo: "erro" };
  } catch {
    return { tipo: "erro" };
  }
}

export async function obterConta(contaId: number): Promise<ResultadoObterConta> {
  try {
    const resposta = await contasObter({ path: { conta_id: contaId } });
    const status = resposta.response?.status;
    if (status === 200 && resposta.data !== undefined) {
      return { tipo: "ok", conta: resposta.data };
    }
    if (status === 401) return { tipo: "sessao_expirada" };
    if (status === 404) return { tipo: "nao_encontrada" };
    return { tipo: "erro" };
  } catch {
    return { tipo: "erro" };
  }
}

/** `versao` é a que a tela leu; se outra edição veio antes, volta "desatualizada". */
export async function editarConta(
  contaId: number,
  versao: number,
  nome: string,
  tipo: TipoConta,
  contaMaeId: number | null,
): Promise<ResultadoEditarConta> {
  try {
    const resposta = await contasEditar({
      path: { conta_id: contaId },
      body: { nome, tipo, conta_mae_id: contaMaeId, versao },
    });
    const status = resposta.response?.status;
    if (status === 200 && resposta.data !== undefined) {
      return { tipo: "ok", conta: resposta.data };
    }
    if (status === 401) return { tipo: "sessao_expirada" };
    if (status === 404) return { tipo: "nao_encontrada" };
    if (status === 409) {
      // Os dois 409 se distinguem pelo código estável do servidor, nunca pelo texto.
      const codigo = resposta.response?.headers.get("X-Abako-Erro");
      return codigo === "AB410" ? { tipo: "nome_repetido" } : { tipo: "desatualizada" };
    }
    if (status === 422) return { tipo: "invalido", mensagem: mensagemDoServidor(resposta.error) };
    return { tipo: "erro" };
  } catch {
    return { tipo: "erro" };
  }
}
