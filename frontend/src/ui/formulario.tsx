// Peças de formulário com acessibilidade: erro ligado ao campo (aria-describedby), campo marcado
// como inválido (aria-invalid) e foco no primeiro campo com problema.
import { useId, useState } from "react";

type Erro = { campo: string | null; mensagem: string };

export type MarcaDeCampo = {
  id: string;
  "aria-invalid": true | undefined;
  "aria-describedby": string | undefined;
};

/**
 * Um erro por vez. `mostrar(campo, texto)` marca o campo, liga a mensagem a ele e põe o foco
 * nele; `mostrarGeral(texto)` é para recusas do servidor que não são de um campo só.
 */
export function useErroDeFormulario() {
  const base = useId();
  const [erro, setErro] = useState<Erro | null>(null);
  const idErro = `${base}-erro`;
  return {
    erro,
    idErro,
    mostrar(campo: string, mensagem: string) {
      setErro({ campo, mensagem });
      document.getElementById(`${base}-${campo}`)?.focus();
    },
    mostrarGeral(mensagem: string) {
      setErro({ campo: null, mensagem });
    },
    limpar() {
      setErro(null);
    },
    /** Props de um campo: `id` (para o rótulo), `aria-invalid` e `aria-describedby`. */
    marcar(campo: string): MarcaDeCampo {
      const comErro = erro?.campo === campo;
      return {
        id: `${base}-${campo}`,
        "aria-invalid": comErro ? true : undefined,
        "aria-describedby": comErro ? idErro : undefined,
      };
    },
  };
}

type AvisoProps = { id?: string; texto: string | null };

/** Mensagem de erro do formulário (anunciada por leitores de tela). */
export function ErroDoFormulario({ id, texto }: AvisoProps) {
  if (texto === null) return null;
  return (
    <p id={id} role="alert" className="erro-form">
      {texto}
    </p>
  );
}
