import { type FormEvent, useId, useState } from "react";

import type { SnapshotSaida } from "../api/gerado";
import { registrarSnapshot } from "../api/saldos";
import { formatarData, hojeEmSaoPaulo } from "../datas";
import { formatarMoeda, lerValorDigitado } from "../dinheiro";

type Props = {
  contaId: number;
  contaNome: string;
  /** Chamado depois de registrar, para a lista buscar o saldo novo no servidor. */
  aoRegistrar: () => void;
  aoSessaoExpirar: () => void;
  aoFechar: () => void;
};

// Convenção do ADR 041 explicada em palavras; o sinal vem pronto da API.
export const SENTIDO_DA_DIVERGENCIA =
  "A diferença é o calculado menos o informado: positiva quer dizer que o abako calculou mais " +
  "do que o banco mostra; negativa, menos.";
// Enquanto não há lançamentos (tasks 09 e 10), a única ação possível é informar de novo.
export const CAUSA_DA_DIVERGENCIA =
  "Quando os lançamentos chegarem ao abako, uma divergência costuma indicar um lançamento que " +
  "faltou ou ficou com valor errado. Por enquanto, sem lançamentos, qualquer saldo diferente do " +
  "anterior aparece como divergência.";

const ERROS = {
  invalido: "O servidor recusou a data ou o valor. A data não pode ser futura nem antes de 2000.",
  conta_nao_encontrada: "Esta conta não foi encontrada. Recarregue a página.",
  erro: "Não foi possível falar com o servidor. Tente de novo.",
} as const;

/**
 * "Informar saldo": o usuário digita o saldo que o app do banco mostra. O servidor guarda
 * (snapshot) e responde se o saldo calculado pelo abako confere. A divergência vem pronta da API;
 * esta tela só a mostra, sem comparar nem corrigir nada (INV-03, INV-23).
 */
export function Snapshot({ contaId, contaNome, aoRegistrar, aoSessaoExpirar, aoFechar }: Props) {
  const id = useId();
  const hoje = hojeEmSaoPaulo();
  const [data, setData] = useState(hoje);
  const [valor, setValor] = useState("");
  const [enviando, setEnviando] = useState(false);
  const [erro, setErro] = useState<string | null>(null);
  const [resultado, setResultado] = useState<SnapshotSaida | null>(null);

  async function enviar(evento: FormEvent<HTMLFormElement>) {
    evento.preventDefault();
    setErro(null);
    setResultado(null);
    const valorApi = lerValorDigitado(valor);
    if (valorApi === null) {
      setErro("Valor não reconhecido. Escreva, por exemplo, 1.234,56 ou -50,00.");
      return;
    }
    setEnviando(true);
    const resposta = await registrarSnapshot(contaId, data, valorApi);
    setEnviando(false);
    if (resposta.tipo === "sessao_expirada") {
      aoSessaoExpirar();
    } else if (resposta.tipo === "ok") {
      setResultado(resposta.snapshot);
      setValor("");
      aoRegistrar();
    } else {
      setErro(ERROS[resposta.tipo]);
    }
  }

  return (
    <form
      onSubmit={enviar}
      className="formulario"
      aria-label={`Informar saldo de ${contaNome}`}
    >
      <p className="texto-suave">
        Abra o app do banco e copie o saldo desta conta. O abako guarda esse valor e confere com o
        saldo que ele calculou pelos lançamentos.
      </p>
      <div className="linha-campos">
        <div className="campo">
          <label htmlFor={`${id}-data`}>Data do saldo</label>
          <input
            id={`${id}-data`}
            type="date"
            value={data}
            min="2000-01-01"
            max={hoje}
            onChange={(e) => setData(e.target.value)}
            required
          />
          <span className="ajuda">O saldo vale para o fim deste dia.</span>
        </div>
        <div className="campo">
          <label htmlFor={`${id}-valor`}>Saldo no banco (R$)</label>
          <input
            id={`${id}-valor`}
            inputMode="decimal"
            autoComplete="off"
            placeholder="1.234,56"
            value={valor}
            onChange={(e) => setValor(e.target.value)}
            required
          />
          <span className="ajuda">Negativo se a conta estiver no vermelho: -50,00.</span>
        </div>
      </div>
      {erro !== null && (
        <p role="alert" className="erro-form">
          {erro}
        </p>
      )}
      {resultado !== null && <ResultadoSnapshot snapshot={resultado} />}
      <div className="acoes">
        <button type="submit" className="botao botao-primario" disabled={enviando}>
          {enviando ? "Salvando…" : "Salvar saldo"}
        </button>
        <button type="button" className="botao botao-secundario" onClick={aoFechar}>
          Fechar
        </button>
      </div>
    </form>
  );
}

/** Mostra o que a API respondeu. Os três casos vêm do servidor; aqui não se calcula nada. */
function ResultadoSnapshot({ snapshot }: { snapshot: SnapshotSaida }) {
  const quando = formatarData(snapshot.data);
  if (snapshot.saldo_inicial) {
    return (
      <div className="resultado" role="status">
        <p>
          <strong>Saldo inicial registrado:</strong> {formatarMoeda(snapshot.valor)} em {quando}.
        </p>
        <p>
          Daqui em diante, cada saldo que você informar é conferido com o calculado. Se depois
          você informar um saldo com data anterior a esta, ele passa a ser o inicial e este passa a
          ser conferido.
        </p>
      </div>
    );
  }
  if (snapshot.divergencia === null || snapshot.saldo_derivado === null) {
    return (
      <div className="resultado" role="status">
        <p>
          <strong>Confere.</strong> O saldo calculado pelo abako em {quando} é igual ao do banco (
          {formatarMoeda(snapshot.valor)}).
        </p>
      </div>
    );
  }
  return (
    <div className="resultado resultado-atencao" role="status">
      <p>
        <strong>Divergência de {formatarMoeda(snapshot.divergencia)}.</strong> Em {quando}, o
        abako calculou {formatarMoeda(snapshot.saldo_derivado)}, mas o banco mostra{" "}
        {formatarMoeda(snapshot.valor)}.
      </p>
      <p>{SENTIDO_DA_DIVERGENCIA}</p>
      <p>
        Nada foi corrigido sozinho: o saldo informado foi guardado e a divergência fica registrada
        em Alertas. Se foi erro de digitação, informe de novo com a mesma data: vale o último.
      </p>
      <p>{CAUSA_DA_DIVERGENCIA}</p>
    </div>
  );
}
