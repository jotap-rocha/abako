import { type FormEvent, useEffect, useId, useRef, useState } from "react";

import type { LancamentoSaida, PessoaSaida, SaldoSaida } from "../api/gerado";
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

/** 1 a 48 parcelas: o número volta da própria lista, sem converter texto em número. */
const OPCOES_PARCELAS: number[] = Array.from({ length: 48 }, (_, i) => i + 1);

type Props = {
  contas: SaldoSaida[];
  /** Pessoas para a compra de terceiro e o repasse (o nome só aparece na tela do dono, ADR 050). */
  pessoas?: PessoaSaida[];
  /**
   * Conta do VR (GET /vale/parametro), se houver. Despesa nesta conta pede o bolso. Só decide se
   * o campo aparece: quem recusa bolso errado é o banco (422), com a mensagem dele.
   */
  contaVrId?: number | null;
  /**
   * Nenhum VR marcado (GET /vale/parametro devolveu nulo). Despesa em conta de benefício aceita
   * então o bolso como opcional, para classificar antes de marcar o VR. O banco decide.
   */
  semVr?: boolean;
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
  parcelas: number;
  pessoaId: number | null;
  /** Vazio = sem bolso (só vale no modo opcional). */
  bolso: Bolso | "";
};

type Bolso = "trabalho" | "pessoal";
const BOLSOS: { valor: Bolso; rotulo: string }[] = [
  { valor: "pessoal", rotulo: "Pessoal" },
  { valor: "trabalho", rotulo: "Trabalho" },
];

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
      parcelas: edicao.parcelas ?? 1,
      pessoaId: edicao.pessoa_id ?? null,
      bolso: BOLSOS.find((b) => b.valor === edicao.bolso)?.valor ?? "",
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
    parcelas: 1,
    pessoaId: null,
    bolso: "",
  };
}

type Campo = "conta" | "destino" | "valor" | "bruto" | "imposto" | "pessoa";
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
  pessoas = [],
  contaVrId = null,
  semVr = false,
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
  // Bolso só na despesa feita na conta do VR; fora dela o campo some e o envio vai sem bolso.
  const ehDespesa = v.tipo === "debito" && v.contaId !== null;
  const pedeBolso = ehDespesa && contaVrId !== null && v.contaId === contaVrId;
  // Sem VR marcado, conta de benefício aceita o bolso (opcional): classificar antes de marcar.
  const bolsoOpcional =
    ehDespesa &&
    semVr &&
    contas.some((c) => c.conta_id === v.contaId && c.conta_beneficio);
  // No VR o padrão é "pessoal"; no modo opcional, vazio (sem bolso).
  const bolsoEscolhido: Bolso | "" = pedeBolso && v.bolso === "" ? "pessoal" : v.bolso;

  function mudar(parcial: Partial<Valores>) {
    // Mudou algo (pessoa, valor, parcelas, tipo...): é outro envio, então chave nova. Sem isso, o
    // servidor devolveria o lançamento antigo como "repetido" se o envio anterior tivesse gravado
    // e só a resposta se perdesse. Sem mudança nenhuma, o retry mantém a mesma chave.
    chave.current = novaChave();
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
    if (info.pessoa === "obrigatoria" && v.pessoaId === null) {
      return { campo: "pessoa", mensagem: "Escolha quem fez o repasse." };
    }
    const base = {
      tipo: v.tipo,
      data: v.data,
      conta_id: v.contaId,
      descricao: v.descricao.trim() === "" ? null : v.descricao,
      // 100% própria (sem pessoa) ou 100% de uma pessoa: o formulário não oferece divisão.
      ...(info.pessoa === null ? {} : { pessoa_id: v.pessoaId }),
      ...(info.pedeParcelas ? { parcelas: v.parcelas } : {}),
      ...((pedeBolso || bolsoOpcional) && bolsoEscolhido !== "" ? { bolso: bolsoEscolhido } : {}),
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
              mudar({
                tipo,
                destinoId: null,
                pessoaId: null,
                parcelas: 1,
                contaId: serve ? v.contaId : null,
              });
            }}
          >
            {TIPOS_LANCAMENTO.map((t) => (
              <option key={t.valor} value={t.valor}>
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
          <label htmlFor={`${id}-valor`}>
            {info.pedeParcelas ? "Valor total da compra (R$)" : "Valor (R$)"}
          </label>
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
          <span className="ajuda">
            {info.pedeParcelas
              ? "O total, mesmo se parcelado: o abako reparte em parcelas e a última absorve os centavos."
              : "Sempre positivo: o tipo diz se entra ou sai."}
          </span>
        </div>
      )}
      {(pedeBolso || bolsoOpcional) && (
        <div className="campo">
          <label htmlFor={`${id}-bolso`}>Bolso</label>
          <select
            id={`${id}-bolso`}
            value={bolsoEscolhido}
            onChange={(e) =>
              mudar({
                bolso: BOLSOS.find((b) => b.valor === e.target.value)?.valor ?? "",
              })
            }
            required={pedeBolso}
          >
            {bolsoOpcional && <option value="">Sem bolso</option>}
            {BOLSOS.map((b) => (
              <option key={b.valor} value={b.valor}>
                {b.rotulo}
              </option>
            ))}
          </select>
          <span className="ajuda">
            {pedeBolso
              ? "Despesa no vale-refeição pertence a um bolso: trabalho ou pessoal. Pessoal é a sugestão."
              : "Opcional. Classifique agora se esta conta será o seu VR (vale-refeição): trabalho ou pessoal."}
          </span>
        </div>
      )}
      {(info.pedeParcelas || info.pessoa !== null) && (
        <div className="linha-campos">
          {info.pedeParcelas && (
            <div className="campo">
              <label htmlFor={`${id}-parcelas`}>Parcelas</label>
              <select
                id={`${id}-parcelas`}
                value={String(v.parcelas)}
                onChange={(e) =>
                  mudar({
                    parcelas: OPCOES_PARCELAS.find((n) => String(n) === e.target.value) ?? 1,
                  })
                }
              >
                {OPCOES_PARCELAS.map((n) => (
                  <option key={n} value={n}>
                    {n === 1 ? "À vista (1x)" : `${n}x`}
                  </option>
                ))}
              </select>
            </div>
          )}
          {info.pessoa !== null && (
            <div className="campo">
              <label htmlFor={`${id}-pessoa`}>
                {info.pessoa === "obrigatoria" ? "Quem repassou" : "De quem é a compra"}
              </label>
              <select
                id={`${id}-pessoa`}
                {...marcar("pessoa")}
                value={v.pessoaId === null ? "" : String(v.pessoaId)}
                onChange={(e) =>
                  mudar({
                    pessoaId: pessoas.find((p) => String(p.pessoa_id) === e.target.value)?.pessoa_id ?? null,
                  })
                }
              >
                {info.pessoa === "obrigatoria" ? (
                  <option value="" disabled>
                    Escolha…
                  </option>
                ) : (
                  <option value="">Minha (compra própria)</option>
                )}
                {pessoas.map((p) => (
                  <option key={p.pessoa_id} value={p.pessoa_id}>
                    {p.nome}
                  </option>
                ))}
              </select>
              <span className="ajuda">
                {info.pessoa === "obrigatoria"
                  ? "Entra na sua conta corrente e abate o que a pessoa deve."
                  : "A compra é toda sua ou toda da pessoa escolhida; não há divisão."}
                {pessoas.length === 0 && " Nenhuma pessoa cadastrada: cadastre em Pessoas."}
              </span>
            </div>
          )}
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
