import type { ReactNode } from "react";
import { Link } from "react-router";

import { type Leitura, obterAlertas, obterGastoReal, obterR2, obterReceita, obterReserva } from "../api/leitura";
import { mesAtual, nomeDoMes } from "../datas";
import { formatarDecimal, formatarMoeda } from "../dinheiro";
import { Termo } from "../leitura/Glossario";
import { Estado } from "../leitura/pecas";
import { ConfigPendente } from "../leitura/Reserva";
import { rotuloDoNivel } from "../leitura/rotulos";
import { AvisoSobraNaoConfiavel } from "../leitura/SobraR2";
import { useCarga } from "../leitura/useCarga";
import { Cartao, Pagina } from "../ui/componentes";

// Cada cartão busca o seu dado: se um falhar, os outros continuam na tela. Funções no nível do
// módulo para a referência não mudar a cada desenho da tela (senão buscaria sem parar).
const buscarReceita = () => obterReceita(mesAtual());
const buscarGasto = () => obterGastoReal(mesAtual());

type CartaoProps<T> = {
  titulo: ReactNode;
  buscar: () => Promise<Leitura<T>>;
  textoErro: string;
  children: (dados: T) => ReactNode;
};

function CartaoDeLeitura<T>({ titulo, buscar, textoErro, children }: CartaoProps<T>) {
  const { estado, recarregar } = useCarga(buscar);
  return (
    <Cartao>
      <h2>{titulo}</h2>
      <Estado
        estado={estado}
        aoTentarDeNovo={recarregar}
        textoCarregando="Carregando…"
        textoErro={textoErro}
      >
        {children}
      </Estado>
    </Cartao>
  );
}

/**
 * Visão geral do mês: receita de caixa, gasto real, sobra do R2, reserva e alertas. Cada número
 * vem pronto da API (ADR 015). O vale não aparece aqui: tem a própria página (ADR 023).
 */
export function Inicio() {
  return (
    <Pagina titulo="Início" descricao={`Visão geral de ${nomeDoMes(mesAtual())}.`}>
      <div className="grade">
        <CartaoDeLeitura
          titulo={<Termo id="receita_caixa">Receita de caixa</Termo>}
          buscar={buscarReceita}
          textoErro="Não foi possível carregar a receita."
        >
          {(receita) => <p className="valor-grande">{formatarMoeda(receita.caixa)}</p>}
        </CartaoDeLeitura>
        <CartaoDeLeitura
          titulo={<Termo id="gasto_real">Gasto real</Termo>}
          buscar={buscarGasto}
          textoErro="Não foi possível carregar o gasto real."
        >
          {(gasto) => (
            <>
              <p className="valor-grande">{formatarMoeda(gasto.total)}</p>
              <Link className="link" to="/gasto-real">
                Ver por conta e outros meses
              </Link>
            </>
          )}
        </CartaoDeLeitura>
        <CartaoDeLeitura
          titulo={<Termo id="sobra">Sobra (R2)</Termo>}
          buscar={obterR2}
          textoErro="Não foi possível carregar a sobra."
        >
          {(r2) => (
            <>
              {r2.pendencias_vencimento > 0 && <AvisoSobraNaoConfiavel />}
              <p className="valor-grande">{formatarMoeda(r2.sobra)}</p>
              <p className="texto-suave">
                Só fatura própria, nos próximos {r2.horizonte_dias} dias.{" "}
                <Link className="link" to="/sobra">
                  Detalhes
                </Link>
              </p>
            </>
          )}
        </CartaoDeLeitura>
        <CartaoDeLeitura
          titulo="Reserva"
          buscar={obterReserva}
          textoErro="Não foi possível carregar a reserva."
        >
          {(reserva) => (
            <>
              {reserva.config_pendente && <ConfigPendente />}
              <p className="valor-grande">{rotuloDoNivel(reserva.nivel)}</p>
              <p className="texto-suave">
                {reserva.cobertura_meses === null
                  ? "Cobertura ainda não calculada. "
                  : `Cobertura de ${formatarDecimal(reserva.cobertura_meses)} meses. `}
                <Link className="link" to="/reserva">
                  Detalhes
                </Link>
              </p>
            </>
          )}
        </CartaoDeLeitura>
      </div>
      <CartaoDeLeitura
        titulo="Alertas"
        buscar={obterAlertas}
        textoErro="Não foi possível carregar os alertas."
      >
        {(alertas) =>
          alertas.itens.length === 0 ? (
            <p className="texto-suave">Nenhum alerta no momento.</p>
          ) : (
            <>
              <ul className="lista-simples" aria-label="Alertas em destaque">
                {alertas.itens.map((a, i) => (
                  <li key={`${a.codigo}-${a.detalhe}-${i}`}>{a.mensagem}</li>
                ))}
              </ul>
              <Link className="link" to="/alertas">
                Ver os alertas
              </Link>
            </>
          )
        }
      </CartaoDeLeitura>
      <p className="texto-suave">
        Saldos de cada conta e cadastro de contas ficam em{" "}
        <Link className="link" to="/contas">
          Contas
        </Link>
        .
      </p>
    </Pagina>
  );
}
