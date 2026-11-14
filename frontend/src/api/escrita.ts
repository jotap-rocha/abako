// Escritas (POST/PUT/DELETE) pelo cliente gerado. Devolve um resultado tipado em vez de lançar,
// para a tela explicar cada caso. Os códigos de erro vêm do cabeçalho `X-Abako-Erro` do servidor
// (nunca do texto da mensagem). Escritas nunca são repetidas aqui: quem tenta de novo é o usuário.

export type Escrita<T> =
  | { tipo: "ok"; dados: T }
  | { tipo: "sessao_expirada" }
  // 409 AB409: o registro mudou desde que a tela o leu.
  | { tipo: "desatualizado" }
  // 409 AB410: nome repetido, vínculo já usado ou compra já estornada.
  | { tipo: "conflito" }
  | { tipo: "nao_encontrado" }
  // 422 AB422: regra do banco; `mensagem` é o `detail` literal, sem dado financeiro.
  | { tipo: "invalido"; mensagem: string | null }
  | { tipo: "erro" };

export type Falha = Exclude<Escrita<unknown>, { tipo: "ok" }>;

type Resposta<T> = { data?: T; error?: unknown; response?: Response };

function mensagemDoServidor(erro: unknown): string | null {
  if (typeof erro === "object" && erro !== null && "detail" in erro) {
    const detalhe = (erro as { detail: unknown }).detail;
    if (typeof detalhe === "string") return detalhe;
  }
  return null;
}

function traduzirFalha(resposta: Resposta<unknown>): Falha {
  const status = resposta.response?.status;
  if (status === 401) return { tipo: "sessao_expirada" };
  if (status === 404) return { tipo: "nao_encontrado" };
  if (status === 409) {
    const codigo = resposta.response?.headers.get("X-Abako-Erro");
    return codigo === "AB410" ? { tipo: "conflito" } : { tipo: "desatualizado" };
  }
  if (status === 422) return { tipo: "invalido", mensagem: mensagemDoServidor(resposta.error) };
  return { tipo: "erro" };
}

/** Escrita que devolve o registro gravado (200 ou 201). */
export async function escrever<T>(chamada: () => Promise<Resposta<T>>): Promise<Escrita<T>> {
  try {
    const resposta = await chamada();
    const status = resposta.response?.status;
    if ((status === 200 || status === 201) && resposta.data !== undefined) {
      return { tipo: "ok", dados: resposta.data };
    }
    return traduzirFalha(resposta);
  } catch {
    return { tipo: "erro" };
  }
}

/** Exclusão (204, sem corpo). */
export async function apagar(chamada: () => Promise<Resposta<unknown>>): Promise<Escrita<null>> {
  try {
    const resposta = await chamada();
    if (resposta.response?.status === 204) return { tipo: "ok", dados: null };
    return traduzirFalha(resposta);
  } catch {
    return { tipo: "erro" };
  }
}
