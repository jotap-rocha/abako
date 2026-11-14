import type { BeneficiosSaida, ContaSaida } from "../api/gerado";
import { formatarMoeda } from "../dinheiro";
import { Cartao, EstadoVazio } from "../ui/componentes";

/**
 * Contas de benefício lado a lado (VR e VA). Só o VR tem bolsos; o VA aparece aqui com receita,
 * despesa e saldo e fica fora do gasto real. Os números vêm da API.
 */
export function Beneficios({
  beneficios,
  contas,
}: {
  beneficios: BeneficiosSaida;
  contas: ContaSaida[];
}) {
  return (
    <Cartao titulo="Contas de benefício">
      {beneficios.itens.length === 0 ? (
        <EstadoVazio
          titulo="Nenhuma conta de benefício"
          texto="Crie uma conta do tipo Benefício em Contas para acompanhar o VR e o VA."
        />
      ) : (
        <ul className="lista" aria-label="Contas de benefício">
          {beneficios.itens.map((b) => (
            <li key={b.conta_id} className="lista-item lista-item-coluna">
              <span className="conta-nome">
                {contas.find((c) => c.conta_id === b.conta_id)?.nome ?? "conta removida"}
                {b.vale_refeicao ? (
                  <span className="etiqueta">vale-refeição</span>
                ) : (
                  <span className="etiqueta etiqueta-neutra">sem bolsos</span>
                )}
              </span>
              <dl className="resumo">
                <div>
                  <dt>Receita do mês</dt>
                  <dd>{formatarMoeda(b.receita_mes)}</dd>
                </div>
                <div>
                  <dt>Despesa do mês</dt>
                  <dd>{formatarMoeda(b.despesa_mes)}</dd>
                </div>
                <div>
                  <dt>Saldo</dt>
                  <dd>{formatarMoeda(b.saldo_total)}</dd>
                </div>
              </dl>
            </li>
          ))}
        </ul>
      )}
    </Cartao>
  );
}
