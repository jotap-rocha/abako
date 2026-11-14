import { useCallback, useState } from "react";

import { listarLancamentos } from "../api/lancamentos";
import { type Leitura, listarContas, listarRecorrentes, obterR2 } from "../api/leitura";
import {
  desvincularOcorrencia,
  excluirRecorrente,
  listarOcorrencias,
  vincularOcorrencia,
} from "../api/recorrentes";
import type {
  ContaSaida,
  LancamentoSaida,
  OcorrenciaSaida,
  RecorrenteSaida,
  SituacaoR2Saida,
} from "../api/gerado";
import { formatarData, mesAtual } from "../datas";
import { formatarMoeda } from "../dinheiro";
import { useCasca } from "../layout/useCasca";
import { Estado, NavegadorMes } from "../leitura/pecas";
import { primeiraFalha, useCarga } from "../leitura/useCarga";
import { rotuloDoTipo } from "../lancamento/tipos";
import { Cartao, EstadoVazio, Pagina } from "../ui/componentes";
import { ConfirmarExclusao } from "../ui/ConfirmarExclusao";
import { textoDaFalha } from "../ui/falhas";
import { FormularioRecorrente } from "./FormularioRecorrente";

const TEXTOS = {
  desatualizado:
    "Este recorrente mudou desde que você o abriu (talvez em outra aba). A lista foi atualizada: confira e tente de novo.",
  conflito: "Esta transação já está ligada a outra ocorrência.",
};

/**
 * Recorrentes: o cadastro (despesas fixas e receitas que se repetem) e as ocorrências do mês.
 * A ocorrência, o valor e o "vencida" vêm do servidor (ADR 048); a tela só exibe e liga/desliga
 * o vínculo com a transação real.
 */
export function Recorrentes() {
  // Mexer no cadastro refaz as ocorrências do mês.
  const [recarga, setRecarga] = useState(0);
  const [mes, setMes] = useState(mesAtual);
  return (
    <Pagina
      titulo="Recorrentes"
      descricao="Despesas fixas e receitas que se repetem todo mês. Elas entram na sobra do R2 até você vincular a transação real."
    >
      <Cadastro aoMudar={() => setRecarga((n) => n + 1)} />
      <Cartao titulo="Ocorrências do mês">
        <NavegadorMes mes={mes} aoMudar={setMes} permitirFuturo rotulo="Mês das ocorrências" />
        {/* `key`: trocar de mês ou mexer no cadastro recria o bloco, sem mostrar dado antigo. */}
        <OcorrenciasDoMes key={`${mes}-${recarga}`} mes={mes} />
      </Cartao>
    </Pagina>
  );
}

// ------------------------------------------------------------------ cadastro

type DadosCadastro = { recorrentes: RecorrenteSaida[]; contas: ContaSaida[] };

async function buscarCadastro(): Promise<Leitura<DadosCadastro>> {
  const [r, c] = await Promise.all([listarRecorrentes(), listarContas()]);
  const falha = primeiraFalha([r, c]);
  if (falha !== null) return falha;
  if (r.tipo !== "ok" || c.tipo !== "ok") return { tipo: "erro" };
  return { tipo: "ok", dados: { recorrentes: r.dados, contas: c.dados } };
}

function Cadastro({ aoMudar }: { aoMudar: () => void }) {
  const { estado, recarregar, atualizar } = useCarga(buscarCadastro);
  const [editando, setEditando] = useState<RecorrenteSaida | null>(null);
  const [excluindo, setExcluindo] = useState<RecorrenteSaida | null>(null);
  const [apagando, setApagando] = useState(false);
  const [erroExclusao, setErroExclusao] = useState<string | null>(null);
  const [aviso, setAviso] = useState<string | null>(null);
  const { aoSessaoExpirar } = useCasca();

  const mudou = useCallback(() => {
    atualizar();
    aoMudar();
  }, [atualizar, aoMudar]);

  async function excluir(lido: RecorrenteSaida) {
    setErroExclusao(null);
    setApagando(true);
    const r = await excluirRecorrente(lido.recorrente_id, lido.versao);
    setApagando(false);
    if (r.tipo === "ok") {
      setExcluindo(null);
      setAviso("Recorrente excluído. O histórico dos vínculos fica guardado.");
      mudou();
    } else if (r.tipo === "sessao_expirada") {
      aoSessaoExpirar();
    } else {
      setErroExclusao(textoDaFalha(r, TEXTOS));
      if (r.tipo === "desatualizado" || r.tipo === "nao_encontrado") mudou();
    }
  }

  return (
    <Estado
      estado={estado}
      aoTentarDeNovo={recarregar}
      textoCarregando="Carregando recorrentes…"
      textoErro="Não foi possível carregar os recorrentes."
    >
      {({ recorrentes, contas }) => {
        const correntes = contas.filter((c) => c.tipo === "corrente" && !c.conta_beneficio);
        const nomeConta = (id: number) =>
          contas.find((c) => c.conta_id === id)?.nome ?? "conta removida";
        return (
          <>
            <Cartao titulo="Novo recorrente">
              <FormularioRecorrente contas={correntes} aoSalvar={mudou} />
            </Cartao>
            {aviso !== null && (
              <p className="resultado" role="status">
                {aviso}
              </p>
            )}
            {recorrentes.length === 0 ? (
              <EstadoVazio
                titulo="Nenhum recorrente ainda"
                texto="Cadastre aluguel, assinatura, salário... O que se repete todo mês."
              />
            ) : (
              <ul className="lista" aria-label="Recorrentes">
                {recorrentes.map((r) => (
                  <li key={r.recorrente_id} className="lista-item lista-item-coluna">
                    <div className="conta-resumo">
                      <span className="conta-nome">
                        {r.nome}
                        <span className="etiqueta">
                          {r.tipo === "receita" ? "receita" : "despesa fixa"}
                        </span>
                      </span>
                      <span className="conta-saldo">{formatarMoeda(r.valor)}</span>
                    </div>
                    <span className="texto-suave">
                      Todo dia {r.dia} · {nomeConta(r.conta_id)} · de {r.mes_inicio}{" "}
                      {r.mes_fim === null ? "sem data final" : `até ${r.mes_fim}`}
                    </span>
                    {editando?.recorrente_id !== r.recorrente_id &&
                      excluindo?.recorrente_id !== r.recorrente_id && (
                        <span className="acoes">
                          <button
                            type="button"
                            className="botao botao-secundario"
                            aria-label={`Editar ${r.nome}`}
                            onClick={() => setEditando(r)}
                          >
                            Editar
                          </button>
                          <button
                            type="button"
                            className="botao botao-secundario"
                            aria-label={`Excluir ${r.nome}`}
                            onClick={() => {
                              setErroExclusao(null);
                              setExcluindo(r);
                            }}
                          >
                            Excluir
                          </button>
                        </span>
                      )}
                    {editando?.recorrente_id === r.recorrente_id && (
                      <FormularioRecorrente
                        contas={correntes}
                        edicao={editando}
                        aoSalvar={() => {
                          setEditando(null);
                          mudou();
                        }}
                        aoFechar={() => setEditando(null)}
                        aoDesatualizado={(mensagem) => {
                          setEditando(null);
                          setAviso(mensagem);
                          mudou();
                        }}
                      />
                    )}
                    {excluindo?.recorrente_id === r.recorrente_id && (
                      <ConfirmarExclusao
                        texto={`Excluir ${r.nome}? Ele deixa de aparecer nas ocorrências; o histórico dos vínculos fica guardado.`}
                        enviando={apagando}
                        erro={erroExclusao}
                        aoConfirmar={() => void excluir(excluindo)}
                        aoCancelar={() => setExcluindo(null)}
                      />
                    )}
                  </li>
                ))}
              </ul>
            )}
          </>
        );
      }}
    </Estado>
  );
}

// ------------------------------------------------------------------ ocorrências

type DadosOcorrencias = {
  ocorrencias: OcorrenciaSaida[];
  lancamentos: LancamentoSaida[];
  r2: SituacaoR2Saida;
};

/** Teto do `GET /api/lancamentos` (limite padrão): ao chegar nele, pode haver mais antigos. */
const TETO_DA_LISTA_DE_LANCAMENTOS = 200;

function buscarOcorrencias(mes: string): () => Promise<Leitura<DadosOcorrencias>> {
  return async () => {
    const [o, l, r2] = await Promise.all([listarOcorrencias(mes), listarLancamentos(), obterR2()]);
    // Lançamentos usa outro formato de resposta: traduz para o mesmo vocabulário de falhas.
    const lancamentos: Leitura<LancamentoSaida[]> =
      l.tipo === "ok" ? { tipo: "ok", dados: l.lancamentos } : { tipo: l.tipo };
    const falha = primeiraFalha([o, lancamentos, r2]);
    if (falha !== null) return falha;
    if (o.tipo !== "ok" || lancamentos.tipo !== "ok" || r2.tipo !== "ok") return { tipo: "erro" };
    return {
      tipo: "ok",
      dados: { ocorrencias: o.dados, lancamentos: lancamentos.dados, r2: r2.dados },
    };
  };
}

function OcorrenciasDoMes({ mes }: { mes: string }) {
  const buscar = useCallback(() => buscarOcorrencias(mes)(), [mes]);
  const { estado, recarregar, atualizar } = useCarga(buscar);
  return (
    <Estado
      estado={estado}
      aoTentarDeNovo={recarregar}
      textoCarregando="Carregando ocorrências…"
      textoErro="Não foi possível carregar as ocorrências."
    >
      {({ ocorrencias, lancamentos, r2 }) =>
        ocorrencias.length === 0 ? (
          <EstadoVazio
            titulo="Nenhuma ocorrência neste mês"
            texto="Nenhum recorrente vale para este mês."
          />
        ) : (
          <>
            {lancamentos.length >= TETO_DA_LISTA_DE_LANCAMENTOS && (
              <p className="texto-suave" role="note">
                A lista de transações para vincular chegou ao limite de{" "}
                {TETO_DA_LISTA_DE_LANCAMENTOS} lançamentos: pode haver lançamentos mais antigos que
                não aparecem aqui.
              </p>
            )}
            {r2.vencidas > 0 && (
              <p className="resultado resultado-atencao" role="status">
                Há {r2.vencidas} ocorrência(s) vencida(s) sem vínculo. Elas ficam fora da sobra do
                R2: vincule a transação que as pagou ou recebeu.
              </p>
            )}
            <ul className="lista" aria-label="Ocorrências">
              {ocorrencias.map((o) => (
                <Ocorrencia
                  key={o.recorrente_id}
                  ocorrencia={o}
                  vencida={r2.itens.some(
                    (i) =>
                      i.grupo === "vencida" &&
                      i.recorrente_id === o.recorrente_id &&
                      i.data === o.data,
                  )}
                  candidatos={lancamentos.filter(
                    (l) =>
                      l.conta_id === o.conta_id &&
                      l.data.startsWith(o.mes) &&
                      (l.estorno_de === null || l.estorno_de === undefined),
                  )}
                  aoMudar={atualizar}
                />
              ))}
            </ul>
          </>
        )
      }
    </Estado>
  );
}

type OcorrenciaProps = {
  ocorrencia: OcorrenciaSaida;
  vencida: boolean;
  /** Lançamentos da mesma conta e do mesmo mês: o servidor confere tipo e conta de verdade. */
  candidatos: LancamentoSaida[];
  aoMudar: () => void;
};

function Ocorrencia({ ocorrencia: o, vencida, candidatos, aoMudar }: OcorrenciaProps) {
  const { aoSessaoExpirar } = useCasca();
  const [escolhendo, setEscolhendo] = useState(false);
  const [escolhida, setEscolhida] = useState<number | null>(null);
  const [enviando, setEnviando] = useState(false);
  const [erro, setErro] = useState<string | null>(null);

  async function ligar() {
    if (escolhida === null) {
      setErro("Escolha a transação que pagou ou recebeu esta ocorrência.");
      return;
    }
    await executar(() => vincularOcorrencia(o.recorrente_id, o.mes, escolhida));
  }

  async function executar(chamada: () => ReturnType<typeof vincularOcorrencia>) {
    setErro(null);
    setEnviando(true);
    const r = await chamada();
    setEnviando(false);
    if (r.tipo === "ok") {
      setEscolhendo(false);
      aoMudar();
    } else if (r.tipo === "sessao_expirada") {
      aoSessaoExpirar();
    } else {
      setErro(textoDaFalha(r, TEXTOS));
    }
  }

  return (
    <li className="lista-item lista-item-coluna">
      <div className="conta-resumo">
        <span className="conta-nome">
          {o.nome}
          <span className="etiqueta">{o.tipo === "receita" ? "receita" : "despesa fixa"}</span>
          {o.vinculada ? (
            <span className="etiqueta etiqueta-neutra">vinculada</span>
          ) : vencida ? (
            <span className="etiqueta">vencida</span>
          ) : (
            <span className="etiqueta etiqueta-neutra">pendente</span>
          )}
        </span>
        <span className="conta-saldo">{formatarMoeda(o.valor)}</span>
      </div>
      <span className="texto-suave">
        {formatarData(o.data)} · esperado {formatarMoeda(o.valor_esperado)}
        {o.vinculada && ` · valor da transação vinculada`}
      </span>
      {!escolhendo && (
        <span className="acoes">
          {o.vinculada ? (
            <button
              type="button"
              className="botao botao-secundario"
              disabled={enviando}
              aria-label={`Desvincular ${o.nome}`}
              onClick={() => void executar(() => desvincularOcorrencia(o.recorrente_id, o.mes))}
            >
              Desvincular
            </button>
          ) : (
            <button
              type="button"
              className="botao botao-secundario"
              aria-label={`Vincular ${o.nome}`}
              onClick={() => {
                setErro(null);
                setEscolhendo(true);
              }}
            >
              Vincular a uma transação
            </button>
          )}
        </span>
      )}
      {escolhendo && (
        <div className="formulario" role="group" aria-label={`Vincular ${o.nome}`}>
          <div className="campo">
            <label htmlFor={`vinculo-${o.recorrente_id}`}>Transação</label>
            <select
              id={`vinculo-${o.recorrente_id}`}
              aria-describedby={erro === null ? undefined : `vinculo-erro-${o.recorrente_id}`}
              value={escolhida === null ? "" : String(escolhida)}
              onChange={(e) =>
                setEscolhida(
                  candidatos.find((l) => String(l.transacao_id) === e.target.value)?.transacao_id ??
                    null,
                )
              }
            >
              <option value="" disabled>
                Escolha…
              </option>
              {candidatos.map((l) => (
                <option key={l.transacao_id} value={l.transacao_id}>
                  {formatarData(l.data)} · {rotuloDoTipo(l.tipo)} · {formatarMoeda(l.valor)}
                  {l.descricao !== null ? ` · ${l.descricao}` : ""}
                </option>
              ))}
            </select>
            {candidatos.length === 0 && (
              <span className="ajuda">
                Nenhum lançamento desta conta neste mês. Registre-o em Lançamentos primeiro.
              </span>
            )}
          </div>
          {erro !== null && (
            <p id={`vinculo-erro-${o.recorrente_id}`} role="alert" className="erro-form">
              {erro}
            </p>
          )}
          <div className="acoes">
            <button
              type="button"
              className="botao botao-primario"
              disabled={enviando}
              onClick={() => void ligar()}
            >
              {enviando ? "Vinculando…" : "Vincular"}
            </button>
            <button
              type="button"
              className="botao botao-secundario"
              onClick={() => setEscolhendo(false)}
            >
              Cancelar
            </button>
          </div>
        </div>
      )}
      {!escolhendo && erro !== null && (
        <p role="alert" className="erro-form">
          {erro}
        </p>
      )}
    </li>
  );
}
