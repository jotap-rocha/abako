import type { TipoConta } from "../api/contas";
import { TIPOS_CONTA, podeTerBanco } from "./tiposConta";

export type ValoresConta = { nome: string; tipo: TipoConta; contaMaeId: number | null };

type Props = {
  /** Prefixo dos `id` dos campos, único na página (o formulário pode aparecer mais de uma vez). */
  id: string;
  valores: ValoresConta;
  aoMudar: (valores: ValoresConta) => void;
  /** Contas correntes que podem ser o banco desta reserva/investimento. */
  bancos: { conta_id: number; nome: string }[];
};

/** Nome, tipo e banco de uma conta: os mesmos campos no cadastro e na edição. */
export function CamposConta({ id, valores, aoMudar, bancos }: Props) {
  const ajuda = TIPOS_CONTA.find((t) => t.valor === valores.tipo)?.ajuda;
  return (
    <>
      <div className="campo">
        <label htmlFor={`${id}-nome`}>Nome da conta</label>
        <input
          id={`${id}-nome`}
          autoComplete="off"
          maxLength={80}
          placeholder="Ex.: Conta principal"
          value={valores.nome}
          onChange={(e) => aoMudar({ ...valores, nome: e.target.value })}
          required
        />
        <span className="ajuda">Um apelido seu. Não informe número de conta nem senha.</span>
      </div>
      <div className="campo">
        <label htmlFor={`${id}-tipo`}>Tipo</label>
        <select
          id={`${id}-tipo`}
          value={valores.tipo}
          onChange={(e) => {
            const tipo = e.target.value as TipoConta;
            aoMudar({ ...valores, tipo, contaMaeId: podeTerBanco(tipo) ? valores.contaMaeId : null });
          }}
        >
          {TIPOS_CONTA.map((t) => (
            <option key={t.valor} value={t.valor}>
              {t.rotulo}
            </option>
          ))}
        </select>
        {ajuda !== undefined && <span className="ajuda">{ajuda}</span>}
      </div>
      {podeTerBanco(valores.tipo) && (
        <div className="campo">
          <label htmlFor={`${id}-banco`}>Pertence ao banco</label>
          <select
            id={`${id}-banco`}
            value={valores.contaMaeId === null ? "" : String(valores.contaMaeId)}
            onChange={(e) =>
              aoMudar({
                ...valores,
                // O id volta da própria lista: nada de converter texto em número.
                contaMaeId: bancos.find((b) => String(b.conta_id) === e.target.value)?.conta_id ?? null,
              })
            }
          >
            <option value="">Nenhum (conta avulsa)</option>
            {bancos.map((b) => (
              <option key={b.conta_id} value={b.conta_id}>
                {b.nome}
              </option>
            ))}
          </select>
          <span className="ajuda">
            Ex.: a caixinha do Banco A pertence à conta corrente do Banco A. O saldo dela continua
            separado.
          </span>
        </div>
      )}
    </>
  );
}
