import { Link } from "react-router";

import type { AlertaSaida, ContaSaida } from "../api/gerado";
import { listarContas, obterAlertas } from "../api/leitura";
import { formatarData, nomeDoMes } from "../datas";
import { formatarDecimal, formatarMoeda } from "../dinheiro";
import { EstadoVazio, Pagina } from "../ui/componentes";
import { Glossario, Termo } from "./Glossario";
import { Estado } from "./pecas";
import {
  ROTA_PARAMETROS,
  acaoSugerida,
  rotuloDaSeveridade,
  rotuloDoBolso,
  rotuloDoNivel,
} from "./rotulos";
import { juntar, useCarga } from "./useCarga";

const buscarAlertas = () => juntar(obterAlertas(), listarContas());

/**
 * Alertas. A lista, a ordem (severidade), o texto e a ação vêm da API, que os deriva a cada
 * consulta (ADR 049). A tela não decide o que é alerta, não dispensa nada e não compara valores.
 * Alerta existe enquanto a condição existe: para sumir, resolva a causa.
 */
export function Alertas() {
  const { estado, recarregar } = useCarga(buscarAlertas);
  return (
    <Pagina titulo="Alertas" descricao="O que pede a sua atenção agora.">
      <Estado
        estado={estado}
        aoTentarDeNovo={recarregar}
        textoCarregando="Carregando alertas…"
        textoErro="Não foi possível carregar os alertas."
      >
        {([alertas, contas]) =>
          alertas.itens.length === 0 ? (
            <EstadoVazio titulo="Nenhum alerta" texto="Nada pede a sua atenção neste momento." />
          ) : (
            <ul className="lista" aria-label="Alertas">
              {alertas.itens.map((alerta, indice) => (
                <li
                  key={`${alerta.codigo}-${alerta.detalhe}-${alerta.r4?.conta_id ?? indice}`}
                  className={
                    alerta.vale === null
                      ? "lista-item lista-item-coluna"
                      : "lista-item lista-item-coluna alerta-forte"
                  }
                >
                  <ItemDeAlerta alerta={alerta} contas={contas} />
                </li>
              ))}
            </ul>
          )
        }
      </Estado>
      <Glossario
        termos={[
          "nivel_reserva",
          "sobra",
          "horizonte",
          "snapshot",
          "divergencia",
          "vale",
          "bolso",
          "resta",
          "sobra_vale",
          "estouro",
        ]}
      />
    </Pagina>
  );
}

/** Um alerta (ou pedido de configuração) com os números do caso, como a API devolveu. */
export function ItemDeAlerta({ alerta, contas }: { alerta: AlertaSaida; contas: ContaSaida[] }) {
  const acao = acaoSugerida(alerta.detalhe);
  const config = alerta.tipo === "configuracao";
  return (
    <>
      <div className="conta-resumo">
        <span className="conta-nome">
          {alerta.mensagem}
          <span className="etiqueta">{alerta.codigo}</span>
          {config ? (
            <span className="etiqueta etiqueta-neutra">pedido de configuração</span>
          ) : (
            <span className="etiqueta etiqueta-neutra">
              severidade {rotuloDaSeveridade(alerta.severidade)}
            </span>
          )}
        </span>
      </div>
      {alerta.reserva !== null && (
        <span className="texto-suave">
          {alerta.reserva.nivel !== null && <>Nível: {rotuloDoNivel(alerta.reserva.nivel)}. </>}
          Saldo líquido {formatarMoeda(alerta.reserva.saldo_liquido)}
          {alerta.reserva.falta !== null && <>, faltam {formatarMoeda(alerta.reserva.falta)}</>}
          {alerta.reserva.cobertura_meses !== null && (
            <>
              , <Termo id="cobertura">cobertura</Termo> de {formatarDecimal(alerta.reserva.cobertura_meses)} meses
            </>
          )}
          .
        </span>
      )}
      {alerta.r2 !== null && (
        <span className="texto-suave">
          <Termo id="sobra">Sobra</Termo> de {formatarMoeda(alerta.r2.sobra)} até{" "}
          {formatarData(alerta.r2.data_fim)} ({alerta.r2.horizonte_dias} dias): disponível{" "}
          {formatarMoeda(alerta.r2.disponivel)}, compromissos {formatarMoeda(alerta.r2.compromissos)}.
          {alerta.r2.vencidas > 0 && <> Ocorrências vencidas: {alerta.r2.vencidas}.</>}
          {alerta.r2.pendencias_vencimento > 0 && (
            <> Cartões sem vencimento ou fechamento: {alerta.r2.pendencias_vencimento}.</>
          )}
        </span>
      )}
      {alerta.r4 !== null && (
        <span className="texto-suave">
          {contas.find((c) => c.conta_id === alerta.r4?.conta_id)?.nome ?? "Conta não encontrada"}:
          em {formatarData(alerta.r4.data_snapshot)}, o abako calculou{" "}
          {formatarMoeda(alerta.r4.saldo_derivado)} e você informou{" "}
          {formatarMoeda(alerta.r4.valor_snapshot)} (<Termo id="divergencia">diferença</Termo>{" "}
          {formatarMoeda(alerta.r4.divergencia)}). Snapshots divergentes na conta:{" "}
          {alerta.r4.quantidade}.
        </span>
      )}
      {alerta.vale !== null && (
        <span className="texto-suave">
          Bolso {rotuloDoBolso(alerta.vale.bolso)} em {nomeDoMes(alerta.vale.mes.slice(0, 7))}:
          alocação {formatarMoeda(alerta.vale.alocacao)}, consumo{" "}
          {formatarMoeda(alerta.vale.consumo)}, <Termo id="resta">resta</Termo>{" "}
          {formatarMoeda(alerta.vale.resta)} (<Termo id="estouro">estouro</Termo>).{" "}
          <Link className="link" to="/vale">
            Ver o vale
          </Link>
        </span>
      )}
      {acao !== null && <span className="texto-suave">O que fazer: {acao}</span>}
      {config && (
        <Link className="link" to={ROTA_PARAMETROS}>
          Configurar
        </Link>
      )}
    </>
  );
}
