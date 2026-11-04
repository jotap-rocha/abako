import { Cartao, EstadoVazio, Pagina } from "../ui/componentes";

/** Visão geral. Os cartões ganham dados nas etapas em que cada regra existir no servidor. */
export function Inicio() {
  return (
    <Pagina titulo="Início" descricao="Visão geral das suas finanças.">
      <div className="grade">
        <Cartao titulo="Saldos">
          <EstadoVazio titulo="Em breve" texto="Os saldos por conta chegam com o saldo derivado." />
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
