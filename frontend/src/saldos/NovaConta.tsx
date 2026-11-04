import { type FormEvent, useState } from "react";

import { criarConta } from "../api/contas";

type Props = {
  /** Chamado depois de criar, para a lista buscar as contas de novo no servidor. */
  aoCriar: () => void;
  aoSessaoExpirar: () => void;
};

const ERROS = {
  nome_repetido: "Já existe uma conta com esse nome. Escolha outro.",
  invalido: "O nome não pode ficar vazio (só espaços) nem passar de 80 caracteres.",
  erro: "Não foi possível falar com o servidor. Tente de novo.",
} as const;

/** Cadastro de conta: só nome e se é benefício. Nenhum dado bancário é pedido (ADR 010). */
export function NovaConta({ aoCriar, aoSessaoExpirar }: Props) {
  const [nome, setNome] = useState("");
  const [beneficio, setBeneficio] = useState(false);
  const [enviando, setEnviando] = useState(false);
  const [erro, setErro] = useState<string | null>(null);
  const [criada, setCriada] = useState<string | null>(null);

  async function enviar(evento: FormEvent<HTMLFormElement>) {
    evento.preventDefault();
    setErro(null);
    setCriada(null);
    setEnviando(true);
    const resposta = await criarConta(nome, beneficio);
    setEnviando(false);
    if (resposta.tipo === "sessao_expirada") {
      aoSessaoExpirar();
    } else if (resposta.tipo === "ok") {
      setCriada(resposta.conta.nome);
      setNome("");
      setBeneficio(false);
      aoCriar();
    } else {
      setErro(ERROS[resposta.tipo]);
    }
  }

  return (
    <form onSubmit={enviar} className="formulario" aria-label="Nova conta">
      <div className="campo">
        <label htmlFor="nova-conta-nome">Nome da conta</label>
        <input
          id="nova-conta-nome"
          autoComplete="off"
          maxLength={80}
          placeholder="Ex.: Conta principal"
          value={nome}
          onChange={(e) => setNome(e.target.value)}
          required
        />
        <span className="ajuda">Um apelido seu. Não informe número de conta nem senha.</span>
      </div>
      <div className="campo-marcar">
        <input
          id="nova-conta-beneficio"
          type="checkbox"
          checked={beneficio}
          onChange={(e) => setBeneficio(e.target.checked)}
        />
        <label htmlFor="nova-conta-beneficio">
          É conta de benefício
          <span className="ajuda">
            Vale-refeição ou vale-alimentação. O que sai dela não conta no gasto real.
          </span>
        </label>
      </div>
      {erro !== null && (
        <p role="alert" className="erro-form">
          {erro}
        </p>
      )}
      {criada !== null && (
        <p className="resultado" role="status">
          Conta “{criada}” criada. Agora use “Informar saldo” nela para registrar o saldo inicial.
        </p>
      )}
      <div className="acoes">
        <button type="submit" className="botao botao-primario" disabled={enviando}>
          {enviando ? "Criando…" : "Criar conta"}
        </button>
      </div>
    </form>
  );
}
