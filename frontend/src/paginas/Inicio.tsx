import { Link } from "react-router";

import { Cartao, EstadoVazio, Pagina } from "../ui/componentes";

/** Visão geral. Os cartões ganham dados nas etapas em que cada regra existir no servidor. */
export function Inicio() {
  return (
    <Pagina titulo="Início" descricao="Visão geral das suas finanças.">
      <div className="grade">
        <Cartao titulo="Saldos">
          <p className="texto-suave">
            O saldo de cada conta e o cadastro de contas ficam em{" "}
            <Link className="link" to="/contas">
              Contas
            </Link>
            .
          </p>
        </Cartao>
        <Cartao titulo="Gasto do mês">
          <EstadoVazio titulo="Em breve" texto="Aparece quando o gasto real estiver pronto." />
        </Cartao>
        <Cartao titulo="Situação do orçamento">
          <EstadoVazio titulo="Em breve" texto="Apertado ou folgado, calculado pelo servidor." />
        </Cartao>
      </div>
    </Pagina>
  );
}
