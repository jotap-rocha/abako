import { type FormEvent, useEffect, useState } from "react";

import { editarConta, obterConta } from "../api/contas";
import { Carregando, MensagemErro } from "../ui/componentes";
import { CamposConta, type ValoresConta } from "./CamposConta";

type Props = {
  contaId: number;
  contaNome: string;
  /** Contas correntes que podem ser o banco desta conta (a própria fica de fora). */
  bancos: { conta_id: number; nome: string }[];
  /** Chamado depois de salvar, para a lista buscar as contas de novo no servidor. */
  aoSalvar: () => void;
  aoSessaoExpirar: () => void;
  aoFechar: () => void;
};

type Estado =
  | { tipo: "carregando" }
  | { tipo: "erro" }
  | { tipo: "pronto"; versao: number; valores: ValoresConta };

/**
 * Editar nome, tipo e banco de uma conta. O servidor guarda uma nova versão; se a conta mudou
 * em outra aba desde que esta tela abriu, ele recusa e a tela pede para reabrir.
 */
export function EditarConta({
  contaId,
  contaNome,
  bancos,
  aoSalvar,
  aoSessaoExpirar,
  aoFechar,
}: Props) {
  const [estado, setEstado] = useState<Estado>({ tipo: "carregando" });
  const [enviando, setEnviando] = useState(false);
  const [erro, setErro] = useState<string | null>(null);
  const [salvo, setSalvo] = useState(false);
  const [tentativa, setTentativa] = useState(0);

  useEffect(() => {
    let ativo = true;
    void obterConta(contaId).then((resposta) => {
      if (!ativo) return;
      if (resposta.tipo === "sessao_expirada") {
        aoSessaoExpirar();
      } else if (resposta.tipo === "ok") {
        const { conta } = resposta;
        setEstado({
          tipo: "pronto",
          versao: conta.versao,
          valores: { nome: conta.nome, tipo: conta.tipo, contaMaeId: conta.conta_mae_id },
        });
      } else {
        setEstado({ tipo: "erro" });
      }
    });
    return () => {
      ativo = false;
    };
  }, [contaId, aoSessaoExpirar, tentativa]);

  async function enviar(evento: FormEvent<HTMLFormElement>) {
    evento.preventDefault();
    if (estado.tipo !== "pronto") return;
    setErro(null);
    setSalvo(false);
    setEnviando(true);
    const { valores, versao } = estado;
    const resposta = await editarConta(
      contaId,
      versao,
      valores.nome,
      valores.tipo,
      valores.contaMaeId,
    );
    setEnviando(false);
    if (resposta.tipo === "sessao_expirada") {
      aoSessaoExpirar();
    } else if (resposta.tipo === "ok") {
      const { conta } = resposta;
      setEstado({
        tipo: "pronto",
        versao: conta.versao,
        valores: { nome: conta.nome, tipo: conta.tipo, contaMaeId: conta.conta_mae_id },
      });
      setSalvo(true);
      aoSalvar();
    } else if (resposta.tipo === "desatualizada") {
      setErro("Esta conta mudou em outra aba. Feche e abra a edição de novo.");
    } else if (resposta.tipo === "nome_repetido") {
      setErro("Já existe uma conta com esse nome. Escolha outro.");
    } else if (resposta.tipo === "invalido") {
      setErro(resposta.mensagem ?? "O servidor recusou a alteração.");
    } else if (resposta.tipo === "nao_encontrada") {
      setErro("Esta conta não foi encontrada. Recarregue a página.");
    } else {
      setErro("Não foi possível falar com o servidor. Tente de novo.");
    }
  }

  if (estado.tipo === "carregando") return <Carregando texto="Carregando a conta…" />;
  if (estado.tipo === "erro") {
    return (
      <MensagemErro
        texto="Não foi possível carregar a conta."
        aoTentarDeNovo={() => {
          setEstado({ tipo: "carregando" });
          setTentativa((n) => n + 1);
        }}
      />
    );
  }
  return (
    <form onSubmit={enviar} className="formulario" aria-label={`Editar conta ${contaNome}`}>
      <CamposConta
        id={`editar-${contaId}`}
        valores={estado.valores}
        aoMudar={(valores) => {
          setSalvo(false);
          setEstado({ ...estado, valores });
        }}
        bancos={bancos.filter((b) => b.conta_id !== contaId)}
      />
      {erro !== null && (
        <p role="alert" className="erro-form">
          {erro}
        </p>
      )}
      {salvo && (
        <p className="resultado" role="status">
          Alteração salva. O saldo e os lançamentos da conta continuam os mesmos.
        </p>
      )}
      <div className="acoes">
        <button type="submit" className="botao botao-primario" disabled={enviando}>
          {enviando ? "Salvando…" : "Salvar conta"}
        </button>
        <button type="button" className="botao botao-secundario" onClick={aoFechar}>
          Fechar
        </button>
      </div>
    </form>
  );
}
