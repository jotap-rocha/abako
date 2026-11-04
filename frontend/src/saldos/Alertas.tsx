import { useCallback, useEffect, useState } from "react";
import { useOutletContext } from "react-router";

import type { DivergenciaSaida } from "../api/gerado";
import { listarDivergencias } from "../api/saldos";
import { formatarData } from "../datas";
import { formatarMoeda } from "../dinheiro";
import type { ContextoCasca } from "../layout/Casca";
import { Cartao, Carregando, EstadoVazio, MensagemErro, Pagina } from "../ui/componentes";
import { CAUSA_DA_DIVERGENCIA, SENTIDO_DA_DIVERGENCIA } from "./Snapshot";

type Estado =
  | { tipo: "carregando" }
  | { tipo: "erro" }
  | { tipo: "ok"; divergencias: DivergenciaSaida[] };

/**
 * Alertas. Por ora só o R4: saldos informados que não bateram com o calculado. A lista e os
 * valores vêm prontos de `GET /api/r4`; a tela não compara nada (ADR 015, INV-23).
 */
export function Alertas() {
  const { aoSessaoExpirar } = useOutletContext<ContextoCasca>();
  const [estado, setEstado] = useState<Estado>({ tipo: "carregando" });

  const carregar = useCallback(async () => {
    setEstado({ tipo: "carregando" });
    const resultado = await listarDivergencias();
    if (resultado.tipo === "sessao_expirada") {
      aoSessaoExpirar();
    } else if (resultado.tipo === "erro") {
      setEstado({ tipo: "erro" });
    } else {
      setEstado({ tipo: "ok", divergencias: resultado.divergencias });
    }
  }, [aoSessaoExpirar]);

  useEffect(() => {
    void carregar();
  }, [carregar]);

  return (
    <Pagina titulo="Alertas" descricao="O que pede a sua atenção.">
      <Cartao titulo="Saldo divergente (R4)">
        <p className="texto-suave">
          Quando o saldo que você informa não bate com o que o abako calculou, ele aparece aqui.
          Nada é corrigido sozinho. {SENTIDO_DA_DIVERGENCIA}
        </p>
        <p className="texto-suave">{CAUSA_DA_DIVERGENCIA}</p>
      </Cartao>
      {estado.tipo === "carregando" && <Carregando texto="Carregando alertas…" />}
      {estado.tipo === "erro" && (
        <MensagemErro
          texto="Não foi possível carregar os alertas."
          aoTentarDeNovo={() => void carregar()}
        />
      )}
      {estado.tipo === "ok" && estado.divergencias.length === 0 && (
        <EstadoVazio
          titulo="Nenhuma divergência"
          texto="Nenhum saldo informado está diferente do calculado."
        />
      )}
      {estado.tipo === "ok" && estado.divergencias.length > 0 && (
        <ul className="lista" aria-label="Saldos divergentes">
          {estado.divergencias.map((d) => (
            <li
              key={`${d.conta_id}-${d.data_snapshot}`}
              className="lista-item lista-item-coluna"
            >
              <div className="conta-resumo">
                <span className="conta-nome">{d.conta_nome}</span>
                <span className="conta-saldo">Diferença: {formatarMoeda(d.divergencia)}</span>
              </div>
              <span className="texto-suave">
                Em {formatarData(d.data_snapshot)}, o abako calculou{" "}
                {formatarMoeda(d.saldo_derivado)} e você informou {formatarMoeda(d.valor_snapshot)}.
              </span>
            </li>
          ))}
        </ul>
      )}
    </Pagina>
  );
}
