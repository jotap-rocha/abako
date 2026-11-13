import { useEffect, useRef } from "react";

import { ErroDoFormulario } from "./formulario";

type Props = {
  texto: string;
  enviando: boolean;
  /** Recusa do servidor (ex.: pessoa com compra vigente), mostrada junto aos botões. */
  erro?: string | null;
  aoConfirmar: () => void;
  aoCancelar: () => void;
};

/** Confirmação antes de excluir. O foco vai para "Cancelar", o caminho seguro. */
export function ConfirmarExclusao({ texto, enviando, erro = null, aoConfirmar, aoCancelar }: Props) {
  const cancelar = useRef<HTMLButtonElement>(null);
  useEffect(() => {
    cancelar.current?.focus();
  }, []);
  return (
    <div className="resultado resultado-atencao" role="group" aria-label="Confirmar exclusão">
      <p>{texto}</p>
      <ErroDoFormulario texto={erro} />
      <span className="acoes">
        <button
          type="button"
          className="botao botao-primario"
          disabled={enviando}
          onClick={aoConfirmar}
        >
          Confirmar exclusão
        </button>
        <button type="button" className="botao botao-secundario" ref={cancelar} onClick={aoCancelar}>
          Cancelar
        </button>
      </span>
    </div>
  );
}
