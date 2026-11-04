// Cadastro de contas pelo cliente gerado. Devolve um resultado tipado em vez de lançar, para a
// tela mostrar uma mensagem clara em cada caso. A lista de contas vem de `listarSaldos`
// (`saldos.ts`), que já traz nome e benefício junto com o saldo.

import { type ContaSaida, contasCriar } from "./gerado";

export type ResultadoCriarConta =
  | { tipo: "ok"; conta: ContaSaida }
  | { tipo: "sessao_expirada" }
  | { tipo: "nome_repetido" }
  | { tipo: "invalido" }
  | { tipo: "erro" };

export async function criarConta(
  nome: string,
  contaBeneficio: boolean,
): Promise<ResultadoCriarConta> {
  try {
    const resposta = await contasCriar({ body: { nome, conta_beneficio: contaBeneficio } });
    const status = resposta.response?.status;
    if (status === 201 && resposta.data !== undefined) {
      return { tipo: "ok", conta: resposta.data };
    }
    if (status === 401) return { tipo: "sessao_expirada" };
    if (status === 409) return { tipo: "nome_repetido" };
    if (status === 422) return { tipo: "invalido" };
    return { tipo: "erro" };
  } catch {
    return { tipo: "erro" };
  }
}
