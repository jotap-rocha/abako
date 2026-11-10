import { type FormEvent, useState } from "react";

import { criarConta } from "../api/contas";
import { CamposConta, type ValoresConta } from "./CamposConta";

type Props = {
  /** Contas correntes que podem ser o banco de uma reserva/investimento. */
  bancos: { conta_id: number; nome: string }[];
  /** Chamado depois de criar, para a lista buscar as contas de novo no servidor. */
  aoCriar: () => void;
  aoSessaoExpirar: () => void;
};

const VAZIO: ValoresConta = { nome: "", tipo: "corrente", contaMaeId: null };

/** Cadastro de conta: nome, tipo e banco. Nenhum dado bancário é pedido (ADR 010). */
export function NovaConta({ bancos, aoCriar, aoSessaoExpirar }: Props) {
  const [valores, setValores] = useState<ValoresConta>(VAZIO);
  const [enviando, setEnviando] = useState(false);
  const [erro, setErro] = useState<string | null>(null);
  const [criada, setCriada] = useState<string | null>(null);

  async function enviar(evento: FormEvent<HTMLFormElement>) {
    evento.preventDefault();
    setErro(null);
    setCriada(null);
    setEnviando(true);
    const resposta = await criarConta(valores.nome, valores.tipo, valores.contaMaeId);
    setEnviando(false);
    if (resposta.tipo === "sessao_expirada") {
      aoSessaoExpirar();
    } else if (resposta.tipo === "ok") {
      setCriada(resposta.conta.nome);
      setValores(VAZIO);
      aoCriar();
    } else if (resposta.tipo === "nome_repetido") {
      setErro("Já existe uma conta com esse nome. Escolha outro.");
    } else if (resposta.tipo === "invalido") {
      setErro(
        resposta.mensagem ??
          "O nome não pode ficar vazio (só espaços) nem passar de 80 caracteres.",
      );
    } else {
      setErro("Não foi possível falar com o servidor. Tente de novo.");
    }
  }

  return (
    <form onSubmit={enviar} className="formulario" aria-label="Nova conta">
      <CamposConta id="nova-conta" valores={valores} aoMudar={setValores} bancos={bancos} />
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
