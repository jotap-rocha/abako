// Única porta do front para a API de sessão. Usa o cliente gerado do OpenAPI (nunca fetch à mão).
// O token CSRF fica só em memória: a página recarregada o recupera por `recuperarSessao`.

import { authEu, authLogin, authLogout } from "./gerado";
import { client } from "./gerado/client.gen";

// Mesma origem da página (a API e o front são servidos juntos, ADR 035).
client.setConfig({ baseUrl: "" });

const METODOS_SEGUROS = new Set(["GET", "HEAD", "OPTIONS"]);
let tokenCsrf: string | null = null;

client.interceptors.request.use((requisicao) => {
  if (tokenCsrf !== null && !METODOS_SEGUROS.has(requisicao.method)) {
    requisicao.headers.set("X-CSRF-Token", tokenCsrf);
  }
  return requisicao;
});

export type ResultadoLogin = "ok" | "credenciais" | "bloqueado" | "erro";

export async function entrar(login: string, senha: string): Promise<ResultadoLogin> {
  try {
    const resposta = await authLogin({ body: { login, senha } });
    if (resposta.response?.status === 200 && resposta.data !== undefined) {
      tokenCsrf = resposta.data.csrf_token;
      return "ok";
    }
    if (resposta.response?.status === 401) return "credenciais";
    if (resposta.response?.status === 429) return "bloqueado";
    return "erro";
  } catch {
    return "erro";
  }
}

/** Há sessão aberta? Também recupera o token CSRF depois de recarregar a página. */
export async function recuperarSessao(): Promise<boolean> {
  try {
    const resposta = await authEu();
    if (resposta.response?.status === 200 && resposta.data !== undefined) {
      tokenCsrf = resposta.data.csrf_token;
      return true;
    }
    return false;
  } catch {
    return false;
  }
}

export async function sair(): Promise<void> {
  try {
    await authLogout();
  } finally {
    tokenCsrf = null;
  }
}
