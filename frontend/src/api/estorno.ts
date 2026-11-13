// Estorno de compra a crédito pelo cliente gerado (ADR 044). O servidor decide quanto foi pago e
// quanto limite volta; esta camada só repassa a resposta.

import { type Escrita, escrever } from "./escrita";
import { type EstornoSaida, lancamentosEstornar } from "./gerado";

/** `versao` é a da compra que a tela leu; `descricao` é opcional. */
export const estornarCompra = (
  transacaoId: number,
  versao: number,
  data: string,
  descricao: string | null,
): Promise<Escrita<EstornoSaida>> =>
  escrever(() =>
    lancamentosEstornar({
      path: { transacao_id: transacaoId },
      body: { versao, data, descricao },
    }),
  );
