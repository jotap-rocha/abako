import type { BolsoSaida, SituacaoValeSaida } from "../api/gerado";
import { formatarMoeda } from "../dinheiro";
import { Termo } from "../leitura/Glossario";
import { rotuloDoDestino } from "../leitura/rotulos";
import { Cartao } from "../ui/componentes";

/** Sinal de menos no texto que a API devolveu: só para destacar, sem nenhuma conta. */
function ehNegativo(valor: string): boolean {
  return valor.startsWith("-");
}

/** Crédito do mês, base de trabalho e saldo total do VR, como a API devolveu. */
export function Resumo({ situacao }: { situacao: SituacaoValeSaida }) {
  return (
    <Cartao titulo="Resumo do mês">
      <dl className="resumo">
        <div>
          <dt>Crédito do mês</dt>
          <dd>{formatarMoeda(situacao.credito)}</dd>
        </div>
        <div>
          <dt>Base de trabalho</dt>
          <dd>{situacao.base_trabalho === null ? "—" : formatarMoeda(situacao.base_trabalho)}</dd>
        </div>
        <div>
          <dt>Saldo total do VR</dt>
          <dd>{situacao.saldo_total === null ? "—" : formatarMoeda(situacao.saldo_total)}</dd>
        </div>
      </dl>
      <p className="texto-suave">
        O saldo total acumula entre os meses; o que resta em cada bolso, não.
      </p>
    </Cartao>
  );
}

/** Os dois bolsos lado a lado. O resta negativo é destacado e nunca compensado pelo outro. */
export function Bolsos({ situacao }: { situacao: SituacaoValeSaida }) {
  return (
    <div className="grade">
      <Bolso nome="Trabalho" bolso={situacao.trabalho} />
      <Bolso nome="Pessoal" bolso={situacao.pessoal} />
    </div>
  );
}

function Bolso({ nome, bolso }: { nome: string; bolso: BolsoSaida }) {
  const estourado = ehNegativo(bolso.resta);
  return (
    <section
      className={estourado ? "cartao bolso-estourado" : "cartao"}
      aria-label={`Bolso ${nome}`}
    >
      <h2>
        Bolso {nome}
        {estourado && <span className="etiqueta etiqueta-forte">estourado</span>}
      </h2>
      <dl className="resumo">
        <div>
          <dt>Alocação inicial</dt>
          <dd>{formatarMoeda(bolso.inicial)}</dd>
        </div>
        <div>
          <dt>Ajuste (sobra do mês anterior)</dt>
          <dd>{formatarMoeda(bolso.ajuste)}</dd>
        </div>
        <div>
          <dt>Alocação efetiva</dt>
          <dd>{formatarMoeda(bolso.alocacao)}</dd>
        </div>
        <div>
          <dt>Consumo</dt>
          <dd>{formatarMoeda(bolso.consumo)}</dd>
        </div>
        <div>
          <dt>
            <Termo id="resta">Resta</Termo>
          </dt>
          <dd className={estourado ? "valor-estouro" : undefined}>
            {formatarMoeda(bolso.resta)}
          </dd>
        </div>
      </dl>
      {estourado && (
        <p className="texto-suave">
          Bolso estourado: gastou mais do que tinha. O estouro não é descontado do outro bolso.
        </p>
      )}
    </section>
  );
}

/** A sobra do mês (calculada pelo servidor) e a explicação de como ela é formada. */
export function Sobra({ situacao }: { situacao: SituacaoValeSaida }) {
  return (
    <Cartao>
      <h2>
        <Termo id="sobra_vale">Sobra do vale</Termo>
      </h2>
      <p className="valor-grande">{formatarMoeda(situacao.sobra)}</p>
      <p className="texto-suave">
        É a soma só dos bolsos com resta positivo, sem compensação: se um bolso estourou, ele não
        diminui a sobra do outro.
        {situacao.decisao_destino !== null && (
          <> Decisão vigente para esta sobra: {rotuloDoDestino(situacao.decisao_destino)}.</>
        )}
      </p>
    </Cartao>
  );
}

/** Receita de caixa, de benefício e total do mês, como a API devolveu. */
export function Receitas({ situacao }: { situacao: SituacaoValeSaida }) {
  return (
    <Cartao titulo="Receita do mês">
      <dl className="resumo">
        <div>
          <dt>Receita de caixa</dt>
          <dd>{formatarMoeda(situacao.receita_caixa)}</dd>
        </div>
        <div>
          <dt>Receita de benefício (VR e VA)</dt>
          <dd>{formatarMoeda(situacao.receita_beneficio)}</dd>
        </div>
        <div>
          <dt>Receita total</dt>
          <dd>{formatarMoeda(situacao.receita_total)}</dd>
        </div>
      </dl>
    </Cartao>
  );
}
