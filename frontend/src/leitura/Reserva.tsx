import type { ReactNode } from "react";
import { Link } from "react-router";

import type { SituacaoSaida } from "../api/gerado";
import { obterReserva } from "../api/leitura";
import { formatarData } from "../datas";
import { formatarDecimal, formatarMoeda } from "../dinheiro";
import { Cartao, Pagina } from "../ui/componentes";
import { Glossario, Termo } from "./Glossario";
import { Estado } from "./pecas";
import { ROTA_PARAMETROS, rotuloDoNivel } from "./rotulos";
import { useCarga } from "./useCarga";

/** Pedido de configuração: não é alerta, só falta o gasto essencial para calcular a meta. */
export function ConfigPendente() {
  return (
    <div className="estado estado-vazio" role="note">
      <strong>Falta configurar a reserva</strong>
      <p>
        Informe o gasto essencial mensal para o abako calcular a meta, o nível e a cobertura da
        reserva.{" "}
        <Link className="link" to={ROTA_PARAMETROS}>
          Configurar a reserva
        </Link>
      </p>
    </div>
  );
}

/**
 * Reserva: nível, falta, cobertura em meses, saldo líquido, imposto, aporte e data-alvo. Tudo
 * calculado pelo servidor (ADR 047, INV-12/17); a tela só exibe o que veio, inclusive o nível.
 */
export function Reserva() {
  const { estado, recarregar } = useCarga(obterReserva);
  return (
    <Pagina titulo="Reserva" descricao="Quanto você tem guardado para imprevistos e se a meta foi atingida.">
      <Estado
        estado={estado}
        aoTentarDeNovo={recarregar}
        textoCarregando="Carregando a reserva…"
        textoErro="Não foi possível carregar a reserva."
      >
        {(reserva) => <DetalheDaReserva reserva={reserva} />}
      </Estado>
      <Glossario termos={["nivel_reserva", "cobertura", "saldo_liquido", "aporte"]} />
    </Pagina>
  );
}

function Linha({ nome, children }: { nome: ReactNode; children: ReactNode }) {
  return (
    <div>
      <dt>{nome}</dt>
      <dd>{children}</dd>
    </div>
  );
}

function DetalheDaReserva({ reserva }: { reserva: SituacaoSaida }) {
  return (
    <>
      {reserva.config_pendente && <ConfigPendente />}
      <Cartao titulo="Situação">
        <dl className="resumo">
          <Linha nome={<Termo id="nivel_reserva">Nível</Termo>}>{rotuloDoNivel(reserva.nivel)}</Linha>
          <Linha nome="Falta para a meta">
            {reserva.falta === null ? "—" : formatarMoeda(reserva.falta)}
          </Linha>
          <Linha nome={<Termo id="cobertura">Cobertura</Termo>}>
            {reserva.cobertura_meses === null ? "—" : `${formatarDecimal(reserva.cobertura_meses)} meses`}
          </Linha>
          <Linha nome="Meta">{reserva.meta === null ? "—" : formatarMoeda(reserva.meta)}</Linha>
        </dl>
      </Cartao>
      <Cartao titulo="Saldo">
        <dl className="resumo">
          <Linha nome={<Termo id="saldo_liquido">Saldo líquido</Termo>}>
            {formatarMoeda(reserva.saldo_liquido)}
          </Linha>
          <Linha nome="Imposto acumulado">{formatarMoeda(reserva.imposto_acumulado)}</Linha>
          <Linha nome="Saldo bruto">{formatarMoeda(reserva.saldo_bruto)}</Linha>
        </dl>
      </Cartao>
      <Cartao titulo="Plano">
        <dl className="resumo">
          <Linha nome={<Termo id="aporte">Aporte mensal</Termo>}>
            {reserva.aporte_mensal === null ? "—" : formatarMoeda(reserva.aporte_mensal)}
          </Linha>
          <Linha nome="Data-alvo">
            {reserva.data_alvo === null ? "—" : formatarData(reserva.data_alvo)}
          </Linha>
        </dl>
        {reserva.alvo_vencida && (
          <p className="texto-suave">A data-alvo já passou; ajuste-a nos parâmetros da reserva.</p>
        )}
      </Cartao>
    </>
  );
}
