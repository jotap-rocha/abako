// Texto, em linguagem direta, para cada resposta que não é sucesso de uma escrita.
import type { Falha } from "../api/escrita";

export type TextosDaFalha = {
  /** 409 AB409: o que mudou desde a leitura. */
  desatualizado: string;
  /** 409 AB410: nome repetido, vínculo já usado, compra já estornada. */
  conflito: string;
  /** Quando a rede falha, o que conferir antes de tentar de novo. */
  erro?: string;
  invalido?: string;
};

const ERRO_PADRAO =
  "Não foi possível falar com o servidor. Confira a tela e tente de novo em instantes.";
const INVALIDO_PADRAO = "O servidor recusou este pedido. Confira os campos.";

/** Não serve para `sessao_expirada`: quem chama volta ao login antes de mostrar texto. */
export function textoDaFalha(falha: Falha, textos: TextosDaFalha): string {
  switch (falha.tipo) {
    case "desatualizado":
      return textos.desatualizado;
    case "conflito":
      return textos.conflito;
    case "nao_encontrado":
      return "Isto não foi encontrado (talvez já tenha sido excluído). A tela foi atualizada.";
    case "invalido":
      // A mensagem literal da regra do banco, quando o servidor a manda.
      return falha.mensagem ?? textos.invalido ?? INVALIDO_PADRAO;
    case "sessao_expirada":
      return "Sua sessão terminou. Entre de novo.";
    case "erro":
      return textos.erro ?? ERRO_PADRAO;
  }
}
