import { Link } from "react-router";

import { EstadoVazio, Pagina } from "../ui/componentes";

export function NaoEncontrada() {
  return (
    <Pagina titulo="Página não encontrada">
      <EstadoVazio titulo="Esse endereço não existe" texto="Confira o endereço ou volte ao início." />
      <p>
        <Link className="link" to="/">
          Ir para o início
        </Link>
      </p>
    </Pagina>
  );
}
