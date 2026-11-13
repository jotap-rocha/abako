import type { ContaSaida } from "../api/gerado";
import {
  gravarFechamento,
  gravarVencimento,
  listarFechamentos,
  listarVencimentos,
} from "../api/vigencias";
import { VigenciaDoCartao } from "./VigenciaDoCartao";

type Props = { cartao: ContaSaida; aoGravar: () => void };

/** Dia de fechamento e dia de vencimento do cartão, cada um com a data desde quando vale. */
export function ConfigCartao({ cartao, aoGravar }: Props) {
  return (
    <>
      <VigenciaDoCartao
        titulo="Dia de fechamento"
        explicacao="O dia em que a fatura fecha: compras depois dele caem na fatura seguinte. Mudar o dia não recalcula compras já feitas."
        cartao={cartao}
        listar={listarFechamentos}
        gravar={gravarFechamento}
        aoGravar={aoGravar}
      />
      <VigenciaDoCartao
        titulo="Dia de vencimento"
        explicacao="O dia em que a fatura vence. Sem ele, a fatura do cartão fica fora da sobra do R2 e a sobra é marcada como não confiável."
        cartao={cartao}
        listar={listarVencimentos}
        gravar={gravarVencimento}
        aoGravar={aoGravar}
      />
    </>
  );
}
