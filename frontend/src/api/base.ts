// Base comum das leituras: traduz o status HTTP num resultado tipado (nunca lança). Fica fora de
// `leitura.ts` para outros módulos de API usarem sem depender dele.

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
export async function ler<T>(chamada: () => Promise<Resposta<T>>): Promise<Leitura<T>> {
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

