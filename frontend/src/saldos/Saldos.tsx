import { useCallback, useEffect, useRef, useState } from "react";
import { useOutletContext } from "react-router";

import type { SaldoSaida } from "../api/gerado";
import { listarSaldos } from "../api/saldos";
import { formatarData } from "../datas";
import { formatarMoeda } from "../dinheiro";
import type { ContextoCasca } from "../layout/Casca";
import { Cartao, Carregando, EstadoVazio, MensagemErro, Pagina } from "../ui/componentes";
import { NovaConta } from "./NovaConta";
import { Snapshot } from "./Snapshot";

type Estado =
  | { tipo: "carregando" }
  | { tipo: "erro" }
  | { tipo: "ok"; saldos: SaldoSaida[] };

/**
 * Contas e saldos. O saldo de cada conta vem pronto de `GET /api/saldos` (calculado no banco);
 * a tela só formata o texto. Depois de criar conta ou informar saldo, busca a lista de novo.
 */
export function Saldos() {
  const { aoSessaoExpirar } = useOutletContext<ContextoCasca>();
  const [estado, setEstado] = useState<Estado>({ tipo: "carregando" });
  const [contaAberta, setContaAberta] = useState<number | null>(null);
  const [falhaAoAtualizar, setFalhaAoAtualizar] = useState(false);
  // Só a resposta do pedido mais recente vale; ao sair da página, nenhuma vale.
  const ultimoPedido = useRef(0);

  // `silencioso`: atualiza sem trocar a lista por "Carregando…", para o resultado do
  // formulário aberto continuar na tela. Se falhar, a lista atual fica e um aviso aparece.
  const carregar = useCallback(
    async (silencioso = false) => {
      const pedido = ++ultimoPedido.current;
      if (!silencioso) setEstado({ tipo: "carregando" });
      const resultado = await listarSaldos();
      if (pedido !== ultimoPedido.current) return;
      if (resultado.tipo === "sessao_expirada") {
        aoSessaoExpirar();
      } else if (resultado.tipo === "erro") {
        if (silencioso) setFalhaAoAtualizar(true);
        else setEstado({ tipo: "erro" });
      } else {
        setFalhaAoAtualizar(false);
        setEstado({ tipo: "ok", saldos: resultado.saldos });
      }
    },
    [aoSessaoExpirar],
  );

  useEffect(() => {
    void carregar();
    return () => {
      ultimoPedido.current += 1;
    };
  }, [carregar]);

  const atualizar = useCallback(() => void carregar(true), [carregar]);

  return (
    <Pagina
      titulo="Contas"
      descricao="Saldo de cada conta, calculado pelo abako a partir do último saldo que você informou."
    >
      {estado.tipo === "carregando" && <Carregando texto="Carregando saldos…" />}
      {estado.tipo === "erro" && (
        <MensagemErro
          texto="Não foi possível carregar os saldos."
          aoTentarDeNovo={() => void carregar()}
        />
      )}
      {estado.tipo === "ok" && falhaAoAtualizar && (
        <MensagemErro
          texto="O que você salvou foi gravado, mas não deu para atualizar a lista."
          aoTentarDeNovo={atualizar}
        />
      )}
      {estado.tipo === "ok" && estado.saldos.length === 0 && (
        <EstadoVazio
          titulo="Nenhuma conta ainda"
          texto="Crie a primeira conta abaixo e depois informe o saldo que o app do banco mostra."
        />
      )}
      {estado.tipo === "ok" && estado.saldos.length > 0 && (
        <ul className="lista" aria-label="Saldos por conta">
          {estado.saldos.map((conta) => (
            <li key={conta.conta_id} className="lista-item lista-item-coluna">
              <div className="conta-resumo">
                <span className="conta-nome">
                  {conta.nome}
                  {conta.conta_beneficio && <span className="etiqueta">Benefício</span>}
                </span>
                <span className="conta-saldo">
                  <span className="so-leitor">Saldo de {conta.nome}: </span>
                  {formatarMoeda(conta.saldo)}
                </span>
              </div>
              <div className="conta-resumo">
                <span className="texto-suave">
                  {conta.snapshot_data === null || conta.snapshot_valor === null
                    ? "Nenhum saldo informado ainda: o valor acima só vê lançamentos."
                    : `Último saldo informado: ${formatarMoeda(conta.snapshot_valor)} em ${formatarData(conta.snapshot_data)}.`}
                </span>
                {contaAberta !== conta.conta_id && (
                  <button
                    type="button"
                    className="botao botao-secundario"
                    onClick={() => setContaAberta(conta.conta_id)}
                    aria-label={`Informar saldo de ${conta.nome}`}
                  >
                    Informar saldo
                  </button>
                )}
              </div>
              {contaAberta === conta.conta_id && (
                <Snapshot
                  contaId={conta.conta_id}
                  contaNome={conta.nome}
                  aoRegistrar={atualizar}
                  aoSessaoExpirar={aoSessaoExpirar}
                  aoFechar={() => setContaAberta(null)}
                />
              )}
            </li>
          ))}
        </ul>
      )}
      {estado.tipo === "ok" && (
        <Cartao titulo="Nova conta">
          <NovaConta aoCriar={atualizar} aoSessaoExpirar={aoSessaoExpirar} />
        </Cartao>
      )}
    </Pagina>
  );
}
