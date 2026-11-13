// Peças comuns das telas de leitura: os 4 estados de uma busca e a troca de mês.
import type { ReactNode } from "react";

import { deslocarMes, mesAtual, nomeDoMes } from "../datas";
import { Carregando, MensagemErro } from "../ui/componentes";
import type { EstadoCarga } from "./useCarga";

type EstadoProps<T> = {
  estado: EstadoCarga<T>;
  aoTentarDeNovo: () => void;
  textoCarregando: string;
  textoErro: string;
  /** Só roda com os dados prontos; o vazio e o sucesso são decididos pela própria tela. */
  children: (dados: T) => ReactNode;
};

/** Mostra "carregando" ou o erro; com dados, entrega-os à tela. */
export function Estado<T>({
  estado,
  aoTentarDeNovo,
  textoCarregando,
  textoErro,
  children,
}: EstadoProps<T>) {
  switch (estado.tipo) {
    case "carregando":
      return <Carregando texto={textoCarregando} />;
    case "invalido":
      return <MensagemErro texto="O servidor não aceitou este pedido (mês inválido)." />;
    case "nao_encontrado":
      return <MensagemErro texto="Não foi encontrado. Recarregue a página." />;
    case "erro":
      return <MensagemErro texto={textoErro} aoTentarDeNovo={aoTentarDeNovo} />;
    case "ok":
      return <>{children(estado.dados)}</>;
  }
}

type MesProps = {
  /** "AAAA-MM". */
  mes: string;
  aoMudar: (mes: string) => void;
  /** Ver meses depois do atual? Faturas sim (parcelas futuras); gasto e receita não. */
  permitirFuturo: boolean;
  rotulo: string;
};

/** Botões "anterior" e "próximo" com o nome do mês no meio. */
export function NavegadorMes({ mes, aoMudar, permitirFuturo, rotulo }: MesProps) {
  // Comparar "AAAA-MM" como texto vale porque o formato é ordenável (sem conta com dinheiro).
  const noLimite = !permitirFuturo && mes >= mesAtual();
  return (
    <div className="navegador-mes" role="group" aria-label={rotulo}>
      <button
        type="button"
        className="botao botao-secundario"
        onClick={() => aoMudar(deslocarMes(mes, -1))}
      >
        Mês anterior
      </button>
      <strong className="navegador-mes-nome" aria-live="polite">
        {nomeDoMes(mes)}
      </strong>
      <button
        type="button"
        className="botao botao-secundario"
        onClick={() => aoMudar(deslocarMes(mes, 1))}
        disabled={noLimite}
      >
        Próximo mês
      </button>
    </div>
  );
}
