import { type FormEvent, useEffect, useId, useRef, useState } from "react";

import { estornarCompra } from "../api/estorno";
import type { EstornoSaida, LancamentoSaida } from "../api/gerado";
import { hojeEmSaoPaulo, nomeDoMes } from "../datas";
import { formatarMoeda } from "../dinheiro";
import { textoDaFalha } from "../ui/falhas";
import { ErroDoFormulario } from "../ui/formulario";

/**
 * Estorno integral = nada da compra estava pago (pago "0.00" na resposta). O front não calcula o
 * pago: só reconhece, pelo texto, o zero que o servidor mandou, para escolher a explicação. O
 * sinal opcional cobre "-0.00" sem aritmética (o NUMERIC do banco não devolve zero negativo, mas
 * a leitura continua certa se algum dia devolver).
 */
export function estornoIntegral(pago: string): boolean {
  return /^-?0+(\.0+)?$/.test(pago);
}

type Props = {
  /** A compra como estava quando o usuário clicou: a versão enviada é a que ele viu (INV-29). */
  compra: LancamentoSaida;
  /** Chamado depois de estornar, para a lista buscar tudo de novo no servidor. */
  aoEstornar: () => void;
  aoSessaoExpirar: () => void;
  aoFechar: () => void;
  /** A compra mudou ou sumiu: quem abriu atualiza a lista e fecha o painel. */
  aoDesatualizado: () => void;
};

/** Painel de estorno de uma compra a crédito (ADR 044). O servidor calcula tudo; aqui se exibe. */
export function Estornar({ compra, aoEstornar, aoSessaoExpirar, aoFechar, aoDesatualizado }: Props) {
  const id = useId();
  const [data, setData] = useState(hojeEmSaoPaulo);
  const [descricao, setDescricao] = useState("");
  const [enviando, setEnviando] = useState(false);
  const [erro, setErro] = useState<string | null>(null);
  const [resultado, setResultado] = useState<EstornoSaida | null>(null);
  // Guarda contra duplo clique: o segundo envio é ignorado enquanto o primeiro está em voo.
  const emVoo = useRef(false);
  const campoData = useRef<HTMLInputElement>(null);
  const botaoFechar = useRef<HTMLButtonElement>(null);

  useEffect(() => {
    campoData.current?.focus();
  }, []);
  // Depois do resultado, o foco vai para "Fechar" (o formulário saiu da tela).
  useEffect(() => {
    if (resultado !== null) botaoFechar.current?.focus();
  }, [resultado]);

  async function enviar(evento: FormEvent<HTMLFormElement>) {
    evento.preventDefault();
    if (emVoo.current) return;
    emVoo.current = true;
    setErro(null);
    setEnviando(true);
    const resposta = await estornarCompra(
      compra.transacao_id,
      compra.versao,
      data,
      descricao.trim() === "" ? null : descricao.trim(),
    );
    emVoo.current = false;
    setEnviando(false);
    if (resposta.tipo === "ok") {
      setResultado(resposta.dados);
      aoEstornar();
    } else if (resposta.tipo === "sessao_expirada") {
      aoSessaoExpirar();
    } else {
      setErro(
        textoDaFalha(resposta, {
          desatualizado:
            "Esta compra mudou desde que você a viu. A lista foi atualizada: abra o estorno de novo.",
          conflito: "Esta compra já foi estornada. Cada compra só pode ser estornada uma vez.",
          erro: "Não foi possível confirmar o estorno. Antes de tentar de novo, confira a lista: se a compra já aparece estornada, o estorno foi feito.",
        }),
      );
      if (resposta.tipo === "desatualizado" || resposta.tipo === "nao_encontrado") aoDesatualizado();
    }
  }

  if (resultado !== null) {
    return <ResultadoDoEstorno resultado={resultado} aoFechar={aoFechar} refFechar={botaoFechar} />;
  }

  return (
    <form
      onSubmit={(e) => void enviar(e)}
      className="formulario resultado resultado-atencao"
      aria-label="Estornar compra"
    >
      <p>
        <strong>Estornar esta compra?</strong> Leia antes de confirmar:
      </p>
      <ul className="lista-simples">
        <li>O estorno é sempre da compra inteira; não existe estorno parcial.</li>
        <li>
          Se nada da compra foi pago, o limite volta por inteiro e nada vai para a conta corrente.
        </li>
        <li>
          Se parte já foi paga, a parte paga vira crédito na próxima fatura aberta e o restante
          devolve limite.
        </li>
        <li>
          Depois de estornar, o cartão fica imutável: nenhum lançamento já gravado nele pode ser
          editado ou excluído, e o estorno não pode ser desfeito.
        </li>
        <li>
          Compra com parte já paga não pode ser editada nem excluída: estorne e lance de novo.
        </li>
      </ul>
      <div className="linha-campos">
        <div className="campo">
          <label htmlFor={`${id}-data`}>Data do estorno</label>
          <input
            id={`${id}-data`}
            ref={campoData}
            type="date"
            value={data}
            min="2000-01-01"
            max={hojeEmSaoPaulo()}
            onChange={(e) => setData(e.target.value)}
            required
          />
          <span className="ajuda">O dia em que o estorno aconteceu. Não pode ser no futuro.</span>
        </div>
        <div className="campo">
          <label htmlFor={`${id}-descricao`}>Descrição (opcional)</label>
          <input
            id={`${id}-descricao`}
            autoComplete="off"
            maxLength={200}
            value={descricao}
            onChange={(e) => setDescricao(e.target.value)}
          />
        </div>
      </div>
      <ErroDoFormulario id={`${id}-erro`} texto={erro} />
      <div className="acoes">
        <button type="submit" className="botao botao-primario" disabled={enviando}>
          {enviando ? "Estornando…" : "Confirmar estorno"}
        </button>
        <button type="button" className="botao botao-secundario" onClick={aoFechar}>
          Cancelar
        </button>
      </div>
    </form>
  );
}

type ResultadoProps = {
  resultado: EstornoSaida;
  aoFechar: () => void;
  refFechar: React.RefObject<HTMLButtonElement | null>;
};

function ResultadoDoEstorno({ resultado, aoFechar, refFechar }: ResultadoProps) {
  const integral = estornoIntegral(resultado.pago);
  return (
    <div className="resultado" role="status" aria-label="Resultado do estorno">
      <p>
        <strong>{integral ? "Estorno integral" : "Estorno com parcelas pagas"}</strong>
      </p>
      {integral ? (
        <p>
          Nada da compra estava pago: o limite voltou por inteiro e nenhum dinheiro foi para a
          conta corrente.
        </p>
      ) : (
        <p>
          Parte da compra já estava paga: a parte paga virou crédito na fatura de{" "}
          {nomeDoMes(resultado.competencia_credito)} (a próxima fatura aberta) e o restante
          devolveu limite.
        </p>
      )}
      <dl className="resumo">
        <div>
          <dt>Total da compra</dt>
          <dd>{formatarMoeda(resultado.total)}</dd>
        </div>
        <div>
          <dt>Já pago (vira crédito)</dt>
          <dd>{formatarMoeda(resultado.pago)}</dd>
        </div>
        <div>
          <dt>Limite devolvido</dt>
          <dd>{formatarMoeda(resultado.limite_devolvido)}</dd>
        </div>
        <div>
          <dt>Fatura que recebe o crédito</dt>
          <dd>{nomeDoMes(resultado.competencia_credito)}</dd>
        </div>
      </dl>
      <div className="acoes">
        <button type="button" className="botao botao-secundario" ref={refFechar} onClick={aoFechar}>
          Fechar
        </button>
      </div>
    </div>
  );
}
