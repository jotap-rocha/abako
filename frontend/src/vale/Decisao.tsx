import { type FormEvent, useId, useState } from "react";

import type { DecisaoHistoricoSaida, SituacaoValeSaida } from "../api/gerado";
import { gravarDecisao } from "../api/vale";
import { useCasca } from "../layout/useCasca";
import { rotuloDoDestino } from "../leitura/rotulos";
import { Cartao } from "../ui/componentes";
import { textoDaFalha } from "../ui/falhas";
import { ErroDoFormulario } from "../ui/formulario";

const DESTINOS = ["trabalho", "pessoal", "nenhum"] as const;

const TEXTOS = {
  desatualizado: "A decisão mudou. A tela foi atualizada: confira e tente de novo.",
  conflito: "Esta decisão entra em conflito com outra já gravada.",
};

/**
 * Decisão da sobra do mês: para onde vai a sobra no mês seguinte. Só se decide em mês encerrado
 * (a API diz por `mes_encerrado`; a tela não compara datas). A decisão não move saldo: só altera
 * a alocação do mês seguinte. Cada gravação é uma versão nova; o histórico fica visível.
 */
export function Decisao({
  situacao,
  historico,
  aoGravar,
}: {
  situacao: SituacaoValeSaida;
  historico: DecisaoHistoricoSaida[];
  aoGravar: () => void;
}) {
  const id = useId();
  const { aoSessaoExpirar } = useCasca();
  const [destino, setDestino] = useState<string>(
    situacao.decisao_destino ?? situacao.destino_padrao,
  );
  const [enviando, setEnviando] = useState(false);
  const [erro, setErro] = useState<string | null>(null);
  const [salvo, setSalvo] = useState<string | null>(null);
  const habilitada = situacao.mes_encerrado;
  const idErro = `${id}-erro`;

  async function enviar(evento: FormEvent<HTMLFormElement>) {
    evento.preventDefault();
    setErro(null);
    setSalvo(null);
    setEnviando(true);
    const r = await gravarDecisao(situacao.mes, destino);
    setEnviando(false);
    if (r.tipo === "ok") {
      setSalvo(`Decisão salva: ${rotuloDoDestino(r.dados.destino)} (versão ${r.dados.versao}).`);
      aoGravar();
    } else if (r.tipo === "sessao_expirada") {
      aoSessaoExpirar();
    } else {
      setErro(textoDaFalha(r, TEXTOS));
    }
  }

  return (
    <Cartao titulo="Decisão da sobra">
      <p className="texto-suave">
        A decisão não move saldo: ela só altera a alocação do bolso escolhido no mês seguinte. Sem
        decisão, a sobra não passa adiante.
      </p>
      {situacao.decisao_destino === null ? (
        <p>Nenhuma decisão gravada para este mês.</p>
      ) : (
        <p>
          Decisão vigente: {rotuloDoDestino(situacao.decisao_destino)}
          {situacao.decisao_versao !== null && <> (versão {situacao.decisao_versao})</>}.
        </p>
      )}
      {!habilitada && (
        <p className="texto-suave">Só dá para decidir depois que o mês termina.</p>
      )}
      <form className="formulario" aria-label="Decisão da sobra" onSubmit={(e) => void enviar(e)}>
        <div className="campo">
          <label htmlFor={`${id}-destino`}>Destino da sobra</label>
          <select
            id={`${id}-destino`}
            value={destino}
            disabled={!habilitada || enviando}
            onChange={(e) => {
              setDestino(DESTINOS.find((d) => d === e.target.value) ?? "nenhum");
              setSalvo(null);
              setErro(null);
            }}
            aria-describedby={erro === null ? undefined : idErro}
          >
            {DESTINOS.map((d) => (
              <option key={d} value={d}>
                {rotuloDoDestino(d)}
              </option>
            ))}
          </select>
          <span className="ajuda">
            Começa pelo destino padrão do parâmetro quando não há decisão.
          </span>
        </div>
        <ErroDoFormulario id={idErro} texto={erro} />
        {salvo !== null && (
          <p className="resultado" role="status">
            {salvo}
          </p>
        )}
        <div className="acoes">
          <button
            type="submit"
            className="botao botao-primario"
            disabled={!habilitada || enviando}
          >
            {enviando ? "Salvando…" : "Salvar decisão"}
          </button>
        </div>
      </form>
      <h3 className="subtitulo">Histórico de decisões</h3>
      {historico.length === 0 ? (
        <p className="texto-suave">Nenhuma versão gravada para este mês.</p>
      ) : (
        <ul className="lista-simples" aria-label="Histórico de decisões">
          {historico.map((h) => (
            <li key={`${h.mes}-${h.versao}`}>
              Versão {h.versao}: {rotuloDoDestino(h.destino)}
              {h.vigente && " (vigente)"}
            </li>
          ))}
        </ul>
      )}
    </Cartao>
  );
}
