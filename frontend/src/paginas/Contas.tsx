import { useCallback, useEffect, useState } from "react";
import { useOutletContext } from "react-router";

import { listarContas } from "../api/contas";
import type { ContaSaida } from "../api/gerado";
import type { ContextoCasca } from "../layout/Casca";
import { Carregando, EstadoVazio, MensagemErro, Pagina } from "../ui/componentes";

type Estado =
  | { tipo: "carregando" }
  | { tipo: "erro" }
  | { tipo: "ok"; contas: ContaSaida[] };

/** Página-modelo dos dados vindos da API: carregando, erro, vazio e sucesso, sempre tratados. */
export function Contas() {
  const { aoSessaoExpirar } = useOutletContext<ContextoCasca>();
  const [estado, setEstado] = useState<Estado>({ tipo: "carregando" });

  const carregar = useCallback(async () => {
    setEstado({ tipo: "carregando" });
    const resultado = await listarContas();
    if (resultado.tipo === "sessao_expirada") {
      aoSessaoExpirar();
    } else if (resultado.tipo === "erro") {
      setEstado({ tipo: "erro" });
    } else {
      setEstado({ tipo: "ok", contas: resultado.contas });
    }
  }, [aoSessaoExpirar]);

  useEffect(() => {
    void carregar();
  }, [carregar]);

  return (
    <Pagina titulo="Contas" descricao="Suas contas e carteiras.">
      {estado.tipo === "carregando" && <Carregando texto="Carregando contas…" />}
      {estado.tipo === "erro" && (
        <MensagemErro
          texto="Não foi possível carregar as contas."
          aoTentarDeNovo={() => void carregar()}
        />
      )}
      {estado.tipo === "ok" && estado.contas.length === 0 && (
        <EstadoVazio
          titulo="Nenhuma conta ainda"
          texto="O cadastro de contas chega nas próximas etapas."
        />
      )}
      {estado.tipo === "ok" && estado.contas.length > 0 && (
        <ul className="lista">
          {estado.contas.map((conta) => (
            <li key={conta.conta_id} className="lista-item">
              <span>{conta.nome}</span>
              {conta.conta_beneficio && <span className="etiqueta">Benefício</span>}
            </li>
          ))}
        </ul>
      )}
    </Pagina>
  );
}
