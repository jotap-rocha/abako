import { type FormEvent, useEffect, useId, useRef, useState } from "react";

import type { LancamentoSaida, SaldoSaida } from "../api/gerado";
import {
  type DadosLancamento,
  type ResultadoGravar,
  type TipoLancamento,
  criarLancamento,
  editarLancamento,
} from "../api/lancamentos";
import { formatarData, hojeEmSaoPaulo } from "../datas";
import { formatarMoeda, lerValorDigitado } from "../dinheiro";
import { novaChave } from "./chave";
import {
  TIPOS_LANCAMENTO,
  contasDeDestino,
  contasDeOrigem,
  infoDoTipo,
  rotuloDoTipo,
} from "./tipos";

type Props = {
  contas: SaldoSaida[];
  /** Se vier, o formulário edita este lançamento (nova versão); senão, cria um. */
  edicao?: LancamentoSaida;
  /** Chamado depois de salvar, para a lista buscar os lançamentos de novo no servidor. */
  aoSalvar: (lancamento: LancamentoSaida) => void;
  aoSessaoExpirar: () => void;
  aoFechar?: () => void;
  /** Edição recusada porque o lançamento mudou: quem abriu atualiza a lista e fecha a edição. */
  aoDesatualizado?: () => void;
};

type Valores = {
  tipo: TipoLancamento;
  data: string;
  valor: string;
  bruto: string;
  imposto: string;
  contaId: number | null;
  destinoId: number | null;
  descricao: string;
};

/** "1234.56" da API vira "1234,56" para editar: só troca o separador, sem conta. */
function paraDigitar(valor: string | null): string {
  return valor === null ? "" : valor.replace(".", ",");
}

function valoresIniciais(contas: SaldoSaida[], edicao?: LancamentoSaida): Valores {
  if (edicao !== undefined) {
    return {
      tipo: edicao.tipo as TipoLancamento,
      data: edicao.data,
      valor: paraDigitar(edicao.valor),
      bruto: paraDigitar(edicao.bruto),
      imposto: paraDigitar(edicao.imposto),
      contaId: edicao.conta_id,
      destinoId: edicao.conta_destino_id,
      descricao: edicao.descricao ?? "",
    };
  }
  return {
    tipo: "debito",
    data: hojeEmSaoPaulo(),
    valor: "",
    bruto: "",
    imposto: "",
    contaId: contas[0]?.conta_id ?? null,
    destinoId: null,
    descricao: "",
  };
}

type Campo = "conta" | "destino" | "valor" | "bruto" | "imposto";
type Problema = { campo: Campo; mensagem: string };

/** Mensagem em linguagem direta para cada resposta que não é sucesso. */
export function mensagemDeErro(resposta: ResultadoGravar): string {
  switch (resposta.tipo) {
    case "invalido":
      return (
        resposta.mensagem ??
        "O servidor recusou este lançamento. Confira a data (sem futuro), o valor e as contas."
      );
    case "desatualizado":
      return "Este lançamento mudou em outra aba. A lista foi atualizada: abra a edição de novo para ver a versão atual.";
    case "nao_encontrado":
      return "Este lançamento não foi encontrado. Recarregue a página.";
    case "excluido":
      return "Esse lançamento já foi excluído. Envie de novo para criar um novo.";
    default:
      return "Não foi possível falar com o servidor. Confira a lista: se o lançamento não aparecer, envie de novo (enviar outra vez não duplica).";
  }
}

/**
 * Formulário de lançamento. Os campos mudam com o tipo (matriz em `tipos.ts`). O valor é sempre
 * positivo: o tipo diz se o dinheiro entra, sai ou muda de conta. Nenhuma conta é feita aqui; o
 * saldo novo vem do servidor. Uma chave de idempotência por lançamento: se o envio falhar por
 * rede, o mesmo botão reenvia com a mesma chave e o servidor não duplica.
 */
export function Formulario({
  contas,
  edicao,
  aoSalvar,
  aoSessaoExpirar,
  aoFechar,
  aoDesatualizado,
}: Props) {
  const id = useId();
  const hoje = hojeEmSaoPaulo();
  const [v, setV] = useState<Valores>(() => valoresIniciais(contas, edicao));
  const [enviando, setEnviando] = useState(false);
  const [erro, setErro] = useState<string | null>(null);
  const [salvo, setSalvo] = useState<string | null>(null);
  // Campo com problema de preenchimento: ganha aria-invalid e o foco (leitores de tela).
  const [campoComErro, setCampoComErro] = useState<Campo | null>(null);
  const chave = useRef(novaChave());
  const formulario = useRef<HTMLFormElement>(null);
  const idErro = `${id}-erro`;

  // Ao abrir a edição, o foco vai para o formulário (o botão que a abriu sumiu da tela).
  useEffect(() => {
    if (edicao !== undefined) formulario.current?.querySelector("select")?.focus();
  }, [edicao]);

  function marcar(campo: Campo) {
    return {
      "aria-invalid": campoComErro === campo ? true : undefined,
      "aria-describedby": campoComErro === campo ? idErro : undefined,
    };
  }

  const info = infoDoTipo(v.tipo);
  const origens = contasDeOrigem(v.tipo, contas);
  const destinos = contasDeDestino(v.tipo, contas, v.contaId);

  function mudar(parcial: Partial<Valores>) {
    setSalvo(null);
    setCampoComErro(null);
    setV((atual) => ({ ...atual, ...parcial }));
  }

  /** Monta o corpo da API a partir do que foi digitado; texto para o usuário se algo não serve. */
  function montar(): DadosLancamento | Problema {
    if (v.contaId === null) return { campo: "conta", mensagem: "Escolha a conta." };
    if (info.pedeDestino && v.destinoId === null) {
      return { campo: "destino", mensagem: "Escolha a conta de destino." };
    }
    const base = {
      tipo: v.tipo,
      data: v.data,
      conta_id: v.contaId,
      descricao: v.descricao.trim() === "" ? null : v.descricao,
    };
    if (info.pedeBrutoEImposto) {
      const bruto = lerValorDigitado(v.bruto);
      const imposto = lerValorDigitado(v.imposto);
      if (bruto === null || imposto === null) {
        return {
          campo: bruto === null ? "bruto" : "imposto",
          mensagem:
            "Valor não reconhecido. Escreva bruto e imposto assim: 12,34 (imposto 0,00 se não houve).",
        };
      }
      if (bruto.startsWith("-") || imposto.startsWith("-")) {
        return {
          campo: bruto.startsWith("-") ? "bruto" : "imposto",
          mensagem: "Digite os valores sem sinal de menos.",
        };
      }
      return { ...base, bruto, imposto, valor: null, conta_destino_id: null };
    }
    const valor = lerValorDigitado(v.valor);
    if (valor === null) {
      return { campo: "valor", mensagem: "Valor não reconhecido. Escreva, por exemplo, 1.234,56." };
    }
    if (valor.startsWith("-")) {
      return {
        campo: "valor",
        mensagem:
          "Digite o valor sem sinal de menos: o tipo do lançamento diz se o dinheiro entra ou sai.",
      };
    }
    return { ...base, valor, conta_destino_id: info.pedeDestino ? v.destinoId : null };
  }

  async function enviar(evento: FormEvent<HTMLFormElement>) {
    evento.preventDefault();
    setErro(null);
    setSalvo(null);
    const dados = montar();
    if ("mensagem" in dados) {
      setErro(dados.mensagem);
      setCampoComErro(dados.campo);
      document.getElementById(`${id}-${dados.campo}`)?.focus();
      return;
    }
    setEnviando(true);
    const resposta =
      edicao === undefined
        ? await criarLancamento(chave.current, dados)
        : await editarLancamento(edicao.transacao_id, edicao.versao, dados);
    setEnviando(false);
    if (resposta.tipo === "sessao_expirada") {
      aoSessaoExpirar();
    } else if (resposta.tipo === "ok") {
      const l = resposta.lancamento;
      chave.current = novaChave();
      // Chave repetida: o servidor devolveu o envio anterior, com os dados de antes.
      const prefixo = resposta.repetido
        ? "Este lançamento já tinha sido salvo antes e foi mantido como estava"
        : edicao === undefined
          ? "Lançamento salvo"
          : "Alteração salva";
      setSalvo(
        `${prefixo}: ${rotuloDoTipo(l.tipo)} de ${formatarMoeda(l.valor)} em ${formatarData(l.data)}.`,
      );
      if (edicao === undefined) setV((atual) => ({ ...atual, valor: "", bruto: "", imposto: "", descricao: "" }));
      aoSalvar(l);
    } else {
      // Rejeição de regra ou de versão: o próximo envio pode ter dados diferentes, então chave
      // nova. Só a falha de rede mantém a chave, para o reenvio não duplicar.
      if (resposta.tipo !== "erro") chave.current = novaChave();
      setErro(mensagemDeErro(resposta));
      if (resposta.tipo === "desatualizado") aoDesatualizado?.();
    }
  }

  const nomeDoFormulario = edicao === undefined ? "Novo lançamento" : "Editar lançamento";

  return (
    <form
      ref={formulario}
      onSubmit={enviar}
      className="formulario"
      aria-label={nomeDoFormulario}
    >
      <div className="linha-campos">
        <div className="campo">
          <label htmlFor={`${id}-tipo`}>Tipo</label>
          <select
            id={`${id}-tipo`}
            value={v.tipo}
            onChange={(e) => {
              const tipo = TIPOS_LANCAMENTO.find((t) => t.valor === e.target.value)?.valor;
              if (tipo === undefined) return;
              // Benefício não entra em transferência nem rendimento: se a conta escolhida não
              // serve ao novo tipo, a escolha volta a "Escolha…" em vez de ficar escondida.
              const serve = contasDeOrigem(tipo, contas).some((c) => c.conta_id === v.contaId);
              mudar({ tipo, destinoId: null, contaId: serve ? v.contaId : null });
            }}
          >
            {TIPOS_LANCAMENTO.map((t) => (
              <option key={t.valor} value={t.valor} disabled={t.emBreve}>
                {t.rotulo}
              </option>
            ))}
          </select>
          <span className="ajuda">{info.ajuda}</span>
        </div>
        <div className="campo">
          <label htmlFor={`${id}-data`}>Data</label>
          <input
            id={`${id}-data`}
            type="date"
            value={v.data}
            min="2000-01-01"
            max={hoje}
            onChange={(e) => mudar({ data: e.target.value })}
            required
          />
          <span className="ajuda">O dia em que aconteceu. Não pode ser no futuro.</span>
        </div>
      </div>
      <div className="linha-campos">
        <div className="campo">
          <label htmlFor={`${id}-conta`}>{info.rotuloConta}</label>
          <select
            id={`${id}-conta`}
            {...marcar("conta")}
            value={v.contaId === null ? "" : String(v.contaId)}
            onChange={(e) =>
              // O id volta da própria lista: nada de converter texto em número.
              mudar({
                contaId: origens.find((c) => String(c.conta_id) === e.target.value)?.conta_id ?? null,
              })
            }
            required
          >
            <option value="" disabled>
              Escolha…
            </option>
            {origens.map((c) => (
              <option key={c.conta_id} value={c.conta_id}>
                {c.nome}
              </option>
            ))}
          </select>
        </div>
        {info.pedeDestino && (
          <div className="campo">
            <label htmlFor={`${id}-destino`}>Conta de destino</label>
            <select
              id={`${id}-destino`}
              {...marcar("destino")}
              value={v.destinoId === null ? "" : String(v.destinoId)}
              onChange={(e) =>
                mudar({
                  destinoId:
                    destinos.find((c) => String(c.conta_id) === e.target.value)?.conta_id ?? null,
                })
              }
              required
            >
              <option value="" disabled>
                Escolha…
              </option>
              {destinos.map((c) => (
                <option key={c.conta_id} value={c.conta_id}>
                  {c.nome}
                </option>
              ))}
            </select>
            {v.tipo === "investimento" && destinos.length === 0 && (
              <span className="ajuda">
                Nenhuma conta de investimento ainda. Crie uma em Contas, com o tipo Investimento.
              </span>
            )}
          </div>
        )}
      </div>
      {info.pedeBrutoEImposto ? (
        <div className="linha-campos">
          <div className="campo">
            <label htmlFor={`${id}-bruto`}>Rendimento bruto (R$)</label>
            <input
              id={`${id}-bruto`}
              {...marcar("bruto")}
              inputMode="decimal"
              autoComplete="off"
              placeholder="12,34"
              value={v.bruto}
              onChange={(e) => mudar({ bruto: e.target.value })}
              required
            />
          </div>
          <div className="campo">
            <label htmlFor={`${id}-imposto`}>Imposto (R$)</label>
            <input
              id={`${id}-imposto`}
              {...marcar("imposto")}
              inputMode="decimal"
              autoComplete="off"
              placeholder="0,00"
              value={v.imposto}
              onChange={(e) => mudar({ imposto: e.target.value })}
              required
            />
            <span className="ajuda">Entra na conta o bruto menos o imposto.</span>
          </div>
        </div>
      ) : (
        <div className="campo">
          <label htmlFor={`${id}-valor`}>Valor (R$)</label>
          <input
            id={`${id}-valor`}
            {...marcar("valor")}
            inputMode="decimal"
            autoComplete="off"
            placeholder="1.234,56"
            value={v.valor}
            onChange={(e) => mudar({ valor: e.target.value })}
            required
          />
          <span className="ajuda">Sempre positivo: o tipo diz se entra ou sai.</span>
        </div>
      )}
      <div className="campo">
        <label htmlFor={`${id}-descricao`}>Descrição (opcional)</label>
        <input
          id={`${id}-descricao`}
          autoComplete="off"
          maxLength={200}
          placeholder="Ex.: mercado do mês"
          value={v.descricao}
          onChange={(e) => mudar({ descricao: e.target.value })}
        />
      </div>
      {erro !== null && (
        <p id={idErro} role="alert" className="erro-form">
          {erro}
        </p>
      )}
      {salvo !== null && (
        <p className="resultado" role="status">
          {salvo}
        </p>
      )}
      <div className="acoes">
        <button type="submit" className="botao botao-primario" disabled={enviando}>
          {enviando ? "Salvando…" : edicao === undefined ? "Salvar lançamento" : "Salvar alteração"}
        </button>
        {aoFechar !== undefined && (
          <button type="button" className="botao botao-secundario" onClick={aoFechar}>
            Fechar
          </button>
        )}
      </div>
    </form>
  );
}
