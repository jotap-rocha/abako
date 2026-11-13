import { useCallback, useEffect, useRef, useState } from "react";
import { useOutletContext } from "react-router";

import type { LancamentoSaida, PessoaSaida, SaldoSaida } from "../api/gerado";
import { excluirLancamento, listarLancamentos } from "../api/lancamentos";
import { listarPessoas } from "../api/leitura";
import { listarSaldos } from "../api/saldos";
import { formatarData } from "../datas";
import { formatarMoeda } from "../dinheiro";
import type { ContextoCasca } from "../layout/Casca";
import { Estornar } from "../estorno/Estornar";
import { Cartao, Carregando, EstadoVazio, MensagemErro, Pagina } from "../ui/componentes";
import { Formulario } from "./Formulario";
import { rotuloDoTipo } from "./tipos";

type Estado =
  | { tipo: "carregando" }
  | { tipo: "erro" }
  | {
      tipo: "ok";
      contas: SaldoSaida[];
      lancamentos: LancamentoSaida[];
      pessoas: PessoaSaida[];
      /** A lista de pessoas não veio: compra de terceiro e repasse ficam sem opções até recarregar. */
      pessoasIndisponiveis: boolean;
    };

/** Lançamento criado por um estorno (liga à compra estornada): não se edita nem se exclui. */
function ehEstorno(l: LancamentoSaida): boolean {
  return l.estorno_de !== null && l.estorno_de !== undefined;
}

/**
 * Lançamentos: formulário de novo lançamento e a lista dos vigentes. Editar cria uma nova versão
 * (a anterior fica no histórico); excluir é lógico. Ambos levam a versão que a tela leu: se ela
 * mudou em outra aba, o servidor recusa e a tela explica. O saldo novo fica em Contas.
 */
export function Lancamentos() {
  const { aoSessaoExpirar } = useOutletContext<ContextoCasca>();
  const [estado, setEstado] = useState<Estado>({ tipo: "carregando" });
  // O lançamento como estava quando a edição/confirmação abriu: a versão enviada é a que o
  // usuário viu, mesmo que a lista seja atualizada por baixo (INV-29).
  const [editando, setEditando] = useState<LancamentoSaida | null>(null);
  const [confirmando, setConfirmando] = useState<LancamentoSaida | null>(null);
  const [estornando, setEstornando] = useState<LancamentoSaida | null>(null);
  const [excluindo, setExcluindo] = useState(false);
  // Para onde o foco volta quando a edição/confirmação fecha (o botão que a abriu sumiu).
  const devolverFoco = useRef<string | null>(null);
  const [aviso, setAviso] = useState<string | null>(null);
  const [falhaAoAtualizar, setFalhaAoAtualizar] = useState(false);
  // Só a resposta do pedido mais recente vale; ao sair da página, nenhuma vale.
  const ultimoPedido = useRef(0);

  const carregar = useCallback(
    async (silencioso = false) => {
      const pedido = ++ultimoPedido.current;
      if (!silencioso) setEstado({ tipo: "carregando" });
      const [contas, lancamentos, pessoas] = await Promise.all([
        listarSaldos(),
        listarLancamentos(),
        listarPessoas(),
      ]);
      if (pedido !== ultimoPedido.current) return;
      if (
        contas.tipo === "sessao_expirada" ||
        lancamentos.tipo === "sessao_expirada" ||
        pessoas.tipo === "sessao_expirada"
      ) {
        aoSessaoExpirar();
      } else if (contas.tipo === "erro" || lancamentos.tipo === "erro") {
        if (silencioso) setFalhaAoAtualizar(true);
        else setEstado({ tipo: "erro" });
      } else {
        setFalhaAoAtualizar(false);
        setEstado({
          tipo: "ok",
          contas: contas.saldos,
          lancamentos: lancamentos.lancamentos,
          pessoas: pessoas.tipo === "ok" ? pessoas.dados : [],
          pessoasIndisponiveis: pessoas.tipo !== "ok",
        });
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

  useEffect(() => {
    if (
      editando !== null ||
      confirmando !== null ||
      estornando !== null ||
      devolverFoco.current === null
    ) {
      return;
    }
    document.querySelector<HTMLElement>(`[data-foco="${devolverFoco.current}"]`)?.focus();
    devolverFoco.current = null;
  }, [editando, confirmando, estornando]);

  // Ao pedir confirmação, o foco vai para "Cancelar" (o caminho seguro).
  useEffect(() => {
    if (confirmando !== null) {
      document.querySelector<HTMLElement>("[data-foco-confirmar]")?.focus();
    }
  }, [confirmando]);

  /** Fecha edição/confirmação e pede o foco de volta no botão do lançamento. */
  function fechar(l: LancamentoSaida, qual: "editar" | "excluir" | "estornar") {
    devolverFoco.current = `${qual}-${l.transacao_id}`;
    setEditando(null);
    setConfirmando(null);
    setEstornando(null);
  }

  const atualizar = useCallback(() => void carregar(true), [carregar]);

  async function excluir(l: LancamentoSaida) {
    setAviso(null);
    setExcluindo(true);
    const resposta = await excluirLancamento(l.transacao_id, l.versao);
    setExcluindo(false);
    devolverFoco.current = `excluir-${l.transacao_id}`;
    setConfirmando(null);
    if (resposta.tipo === "sessao_expirada") {
      aoSessaoExpirar();
    } else if (resposta.tipo === "ok") {
      setAviso("Lançamento excluído. Ele deixa de contar no saldo; o histórico fica guardado.");
      atualizar();
    } else if (resposta.tipo === "desatualizado") {
      setAviso("Este lançamento mudou em outra aba. A lista foi atualizada: confira e tente de novo.");
      atualizar();
    } else if (resposta.tipo === "nao_encontrado") {
      setAviso("Este lançamento não existe mais. A lista foi atualizada.");
      atualizar();
    } else {
      setAviso("Não foi possível excluir agora. Tente de novo.");
    }
  }

  return (
    <Pagina
      titulo="Lançamentos"
      descricao="Registre o que entra, sai ou muda de conta. O saldo de cada conta está em Contas."
    >
      {estado.tipo === "carregando" && <Carregando texto="Carregando lançamentos…" />}
      {estado.tipo === "erro" && (
        <MensagemErro
          texto="Não foi possível carregar os lançamentos."
          aoTentarDeNovo={() => void carregar()}
        />
      )}
      {estado.tipo === "ok" && falhaAoAtualizar && (
        <MensagemErro
          texto="O que você salvou foi gravado, mas não deu para atualizar a lista."
          aoTentarDeNovo={atualizar}
        />
      )}
      {estado.tipo === "ok" && estado.pessoasIndisponiveis && (
        <MensagemErro
          texto="Não foi possível carregar as pessoas. Compra de terceiro e repasse ficam sem opções até recarregar."
          aoTentarDeNovo={atualizar}
        />
      )}
      {estado.tipo === "ok" && estado.contas.length === 0 && (
        <EstadoVazio
          titulo="Crie uma conta primeiro"
          texto="Todo lançamento pertence a uma conta. Crie a primeira em Contas."
        />
      )}
      {estado.tipo === "ok" && estado.contas.length > 0 && (
        <Cartao titulo="Novo lançamento">
          <Formulario
            contas={estado.contas}
            pessoas={estado.pessoas}
            aoSalvar={atualizar}
            aoSessaoExpirar={aoSessaoExpirar}
          />
        </Cartao>
      )}
      {aviso !== null && (
        <p className="resultado" role="status">
          {aviso}
        </p>
      )}
      {estado.tipo === "ok" && estado.contas.length > 0 && estado.lancamentos.length === 0 && (
        <EstadoVazio titulo="Nenhum lançamento ainda" texto="Use o formulário acima para o primeiro." />
      )}
      {estado.tipo === "ok" && estado.lancamentos.length > 0 && (
        <ul className="lista" aria-label="Lançamentos">
          {estado.lancamentos.map((l) => {
            const nome = (id: number | null) =>
              estado.contas.find((c) => c.conta_id === id)?.nome ?? "conta removida";
            // Sem a lista de pessoas não dá para dizer que a pessoa foi removida: texto neutro.
            const nomeDaPessoa = (id: number) =>
              estado.pessoas.find((p) => p.pessoa_id === id)?.nome ??
              (estado.pessoasIndisponiveis ? "pessoa" : "pessoa removida");
            return (
              <li key={l.transacao_id} className="lista-item lista-item-coluna">
                <div className="conta-resumo">
                  <span className="conta-nome">
                    {ehEstorno(l) ? "Estorno de compra" : rotuloDoTipo(l.tipo)}
                    <span className="etiqueta">{formatarData(l.data)}</span>
                    {l.parcelas !== null && l.parcelas !== undefined && l.parcelas > 1 && (
                      <span className="etiqueta etiqueta-neutra">{l.parcelas}x</span>
                    )}
                  </span>
                  <span className="conta-saldo">
                    <span className="so-leitor">Valor: </span>
                    {formatarMoeda(l.valor)}
                  </span>
                </div>
                <span className="texto-suave">
                  {nome(l.conta_id)}
                  {l.conta_destino_id !== null && ` → ${nome(l.conta_destino_id)}`}
                  {l.bruto !== null &&
                    l.imposto !== null &&
                    ` · bruto ${formatarMoeda(l.bruto)}, imposto ${formatarMoeda(l.imposto)}`}
                  {l.pessoa_id != null &&
                    ` · ${l.tipo === "repasse" ? "repasse de" : "compra de"} ${nomeDaPessoa(l.pessoa_id)}`}
                  {l.estorno_credito != null &&
                    ` · crédito na fatura ${formatarMoeda(l.estorno_credito)}`}
                  {l.descricao !== null && ` · ${l.descricao}`}
                </span>
                {editando?.transacao_id !== l.transacao_id &&
                  confirmando?.transacao_id !== l.transacao_id &&
                  estornando?.transacao_id !== l.transacao_id && (
                  <span className="acoes">
                    {!ehEstorno(l) && (
                      <button
                        type="button"
                        className="botao botao-secundario"
                        aria-label={`Editar lançamento de ${formatarData(l.data)} (${formatarMoeda(l.valor)})`}
                        data-foco={`editar-${l.transacao_id}`}
                        onClick={() => setEditando(l)}
                      >
                        Editar
                      </button>
                    )}
                    {l.tipo === "credito" && !ehEstorno(l) && (
                      <button
                        type="button"
                        className="botao botao-secundario"
                        aria-label={`Estornar compra de ${formatarData(l.data)} (${formatarMoeda(l.valor)})`}
                        data-foco={`estornar-${l.transacao_id}`}
                        onClick={() => setEstornando(l)}
                      >
                        Estornar
                      </button>
                    )}
                    <button
                      type="button"
                      className="botao botao-secundario"
                      aria-label={`Excluir lançamento de ${formatarData(l.data)} (${formatarMoeda(l.valor)})`}
                      data-foco={`excluir-${l.transacao_id}`}
                      onClick={() => setConfirmando(l)}
                    >
                      Excluir
                    </button>
                  </span>
                )}
                {confirmando?.transacao_id === l.transacao_id && (
                  <div className="resultado resultado-atencao" role="group" aria-label="Confirmar exclusão">
                    <p>Excluir este lançamento? Ele deixa de contar no saldo; o histórico fica guardado.</p>
                    <span className="acoes">
                      <button
                        type="button"
                        className="botao botao-primario"
                        disabled={excluindo}
                        onClick={() => void excluir(confirmando)}
                      >
                        Confirmar exclusão
                      </button>
                      <button
                        type="button"
                        className="botao botao-secundario"
                        data-foco-confirmar=""
                        onClick={() => fechar(l, "excluir")}
                      >
                        Cancelar
                      </button>
                    </span>
                  </div>
                )}
                {estornando?.transacao_id === l.transacao_id && (
                  <Estornar
                    compra={estornando}
                    aoEstornar={atualizar}
                    aoSessaoExpirar={aoSessaoExpirar}
                    aoFechar={() => fechar(l, "estornar")}
                    aoDesatualizado={() => {
                      setEstornando(null);
                      setAviso(
                        "Esta compra mudou ou já foi estornada. A lista foi atualizada: confira antes de tentar de novo.",
                      );
                      atualizar();
                    }}
                  />
                )}
                {editando?.transacao_id === l.transacao_id && (
                  <Formulario
                    contas={estado.contas}
                    pessoas={estado.pessoas}
                    edicao={editando}
                    aoSalvar={() => {
                      fechar(l, "editar");
                      atualizar();
                    }}
                    aoSessaoExpirar={aoSessaoExpirar}
                    aoFechar={() => fechar(l, "editar")}
                    aoDesatualizado={() => {
                      setEditando(null);
                      setAviso(
                        "Este lançamento mudou em outra aba. A lista foi atualizada: abra a edição de novo.",
                      );
                      atualizar();
                    }}
                  />
                )}
              </li>
            );
          })}
        </ul>
      )}
    </Pagina>
  );
}
