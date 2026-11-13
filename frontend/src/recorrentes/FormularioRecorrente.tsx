import { type FormEvent, useState } from "react";

import { type DadosRecorrente, criarRecorrente, editarRecorrente } from "../api/recorrentes";
import type { ContaSaida, RecorrenteSaida } from "../api/gerado";
import { mesAtual } from "../datas";
import { lerValorDigitado } from "../dinheiro";
import { lerInteiro } from "../inteiro";
import { useCasca } from "../layout/useCasca";
import { textoDaFalha } from "../ui/falhas";
import { ErroDoFormulario, useErroDeFormulario } from "../ui/formulario";

// Caracteres de controle (tabulação, quebra de linha, NUL...) sujariam listas e telas.
const CARACTER_DE_CONTROLE = /[\u0000-\u001f\u007f-\u009f]/;

type Props = {
  /** Contas correntes onde o recorrente pode cair (o servidor recusa as demais). */
  contas: ContaSaida[];
  /** Se vier, edita este recorrente (nova versão); senão, cria um. */
  edicao?: RecorrenteSaida;
  aoSalvar: () => void;
  aoFechar?: () => void;
  /** Edição recusada porque o recorrente mudou: quem abriu atualiza a lista e fecha a edição. */
  aoDesatualizado?: (mensagem: string) => void;
};

const TEXTOS = {
  desatualizado:
    "Este recorrente mudou desde que você o abriu (talvez em outra aba). A lista foi atualizada: abra a edição de novo.",
  conflito: "Já existe um recorrente com esse nome.",
};

/** Cadastro e edição de recorrente (despesa fixa ou receita que se repete todo mês, ADR 048). */
export function FormularioRecorrente({ contas, edicao, aoSalvar, aoFechar, aoDesatualizado }: Props) {
  const { aoSessaoExpirar } = useCasca();
  const form = useErroDeFormulario();
  const [nome, setNome] = useState(edicao?.nome ?? "");
  const [tipo, setTipo] = useState<"fixo" | "receita">(edicao?.tipo === "receita" ? "receita" : "fixo");
  const [valor, setValor] = useState(edicao === undefined ? "" : edicao.valor.replace(".", ","));
  const [dia, setDia] = useState(edicao === undefined ? "" : String(edicao.dia));
  const [contaId, setContaId] = useState<number | null>(edicao?.conta_id ?? contas[0]?.conta_id ?? null);
  const [mesInicio, setMesInicio] = useState(edicao?.mes_inicio ?? mesAtual());
  const [mesFim, setMesFim] = useState(edicao?.mes_fim ?? "");
  const [enviando, setEnviando] = useState(false);
  const [salvo, setSalvo] = useState<string | null>(null);

  function montar(): DadosRecorrente | { campo: string; mensagem: string } {
    const limpo = nome.trim();
    if (limpo === "") return { campo: "nome", mensagem: "Escreva o nome do recorrente." };
    if (CARACTER_DE_CONTROLE.test(limpo)) {
      return {
        campo: "nome",
        mensagem: "O nome não pode ter caracteres de controle (como tabulação). Escreva só texto comum.",
      };
    }
    const valorTexto = lerValorDigitado(valor);
    if (valorTexto === null || valorTexto.startsWith("-")) {
      return {
        campo: "valor",
        mensagem: "Valor não reconhecido. Escreva, sem sinal de menos, por exemplo 1.234,56.",
      };
    }
    const diaNumero = lerInteiro(dia, 1, 31);
    if (diaNumero === null) {
      return { campo: "dia", mensagem: "O dia do mês vai de 1 a 31." };
    }
    if (contaId === null) return { campo: "conta", mensagem: "Escolha a conta corrente." };
    if (mesInicio === "") return { campo: "inicio", mensagem: "Escolha o mês em que começa." };
    return {
      nome: limpo,
      tipo,
      valor: valorTexto,
      dia: diaNumero,
      conta_id: contaId,
      mes_inicio: mesInicio,
      mes_fim: mesFim === "" ? null : mesFim,
    };
  }

  async function enviar(evento: FormEvent<HTMLFormElement>) {
    evento.preventDefault();
    form.limpar();
    setSalvo(null);
    const dados = montar();
    if ("mensagem" in dados) {
      form.mostrar(dados.campo, dados.mensagem);
      return;
    }
    setEnviando(true);
    const r =
      edicao === undefined
        ? await criarRecorrente(dados)
        : await editarRecorrente(edicao.recorrente_id, edicao.versao, dados);
    setEnviando(false);
    if (r.tipo === "ok") {
      if (edicao === undefined) {
        setNome("");
        setValor("");
        setDia("");
        setSalvo("Recorrente cadastrado.");
      }
      aoSalvar();
    } else if (r.tipo === "sessao_expirada") {
      aoSessaoExpirar();
    } else {
      const texto = textoDaFalha(r, TEXTOS);
      form.mostrarGeral(texto);
      // A edição fecha e some daqui: a mensagem sobe para quem a abriu.
      if (r.tipo === "desatualizado" || r.tipo === "nao_encontrado") aoDesatualizado?.(texto);
    }
  }

  function mudou() {
    setSalvo(null);
    form.limpar();
  }

  return (
    <form
      className="formulario"
      aria-label={edicao === undefined ? "Novo recorrente" : "Editar recorrente"}
      onSubmit={(e) => void enviar(e)}
    >
      <div className="linha-campos">
        <div className="campo">
          <label htmlFor={form.marcar("nome").id}>Nome</label>
          <input
            {...form.marcar("nome")}
            maxLength={80}
            autoComplete="off"
            placeholder="Ex.: aluguel"
            value={nome}
            onChange={(e) => {
              setNome(e.target.value);
              mudou();
            }}
          />
        </div>
        <div className="campo">
          <label htmlFor={form.marcar("tipo").id}>Tipo</label>
          <select
            {...form.marcar("tipo")}
            value={tipo}
            onChange={(e) => {
              setTipo(e.target.value === "receita" ? "receita" : "fixo");
              mudou();
            }}
          >
            <option value="fixo">Despesa fixa (sai da conta)</option>
            <option value="receita">Receita (entra na conta)</option>
          </select>
        </div>
      </div>
      <div className="linha-campos">
        <div className="campo">
          <label htmlFor={form.marcar("valor").id}>Valor esperado (R$)</label>
          <input
            {...form.marcar("valor")}
            inputMode="decimal"
            autoComplete="off"
            placeholder="1.234,56"
            value={valor}
            onChange={(e) => {
              setValor(e.target.value);
              mudou();
            }}
          />
          <span className="ajuda">Sempre positivo. Vale até você vincular a transação real.</span>
        </div>
        <div className="campo">
          <label htmlFor={form.marcar("dia").id}>Dia do mês</label>
          <input
            {...form.marcar("dia")}
            inputMode="numeric"
            autoComplete="off"
            placeholder="5"
            value={dia}
            onChange={(e) => {
              setDia(e.target.value);
              mudou();
            }}
          />
          <span className="ajuda">
            De 1 a 31. Em mês sem esse dia, vale o último dia do mês.
          </span>
        </div>
      </div>
      <div className="campo">
        <label htmlFor={form.marcar("conta").id}>Conta corrente</label>
        <select
          {...form.marcar("conta")}
          value={contaId === null ? "" : String(contaId)}
          onChange={(e) => {
            setContaId(contas.find((c) => String(c.conta_id) === e.target.value)?.conta_id ?? null);
            mudou();
          }}
        >
          <option value="" disabled>
            Escolha…
          </option>
          {contas.map((c) => (
            <option key={c.conta_id} value={c.conta_id}>
              {c.nome}
            </option>
          ))}
        </select>
        {contas.length === 0 && (
          <span className="ajuda">Nenhuma conta corrente ainda. Crie uma em Contas.</span>
        )}
      </div>
      <div className="linha-campos">
        <div className="campo">
          <label htmlFor={form.marcar("inicio").id}>Começa em (mês)</label>
          <input
            {...form.marcar("inicio")}
            type="month"
            value={mesInicio}
            onChange={(e) => {
              setMesInicio(e.target.value);
              mudou();
            }}
          />
        </div>
        <div className="campo">
          <label htmlFor={form.marcar("fim").id}>Termina em (mês, opcional)</label>
          <input
            {...form.marcar("fim")}
            type="month"
            value={mesFim}
            onChange={(e) => {
              setMesFim(e.target.value);
              mudou();
            }}
          />
          <span className="ajuda">Deixe vazio se não tem data para acabar.</span>
        </div>
      </div>
      <ErroDoFormulario id={form.idErro} texto={form.erro?.mensagem ?? null} />
      {salvo !== null && (
        <p className="resultado" role="status">
          {salvo}
        </p>
      )}
      <div className="acoes">
        <button type="submit" className="botao botao-primario" disabled={enviando}>
          {enviando
            ? "Salvando…"
            : edicao === undefined
              ? "Cadastrar recorrente"
              : "Salvar alteração"}
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
