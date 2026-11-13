import { type FormEvent, type ReactNode, useCallback, useState } from "react";

import type { Leitura } from "../api/base";
import type { Escrita } from "../api/escrita";
import type { ContaSaida } from "../api/gerado";
import { formatarData, hojeEmSaoPaulo } from "../datas";
import { lerInteiro } from "../inteiro";
import { useCasca } from "../layout/useCasca";
import { Estado } from "../leitura/pecas";
import { useCarga } from "../leitura/useCarga";
import { Cartao } from "../ui/componentes";
import { textoDaFalha } from "../ui/falhas";
import { ErroDoFormulario, useErroDeFormulario } from "../ui/formulario";

type Vigencia = { dia: number; vigente_desde: string };

type Props = {
  /** "Dia de fechamento" ou "Dia de vencimento". */
  titulo: string;
  explicacao: ReactNode;
  cartao: ContaSaida;
  listar: (contaId: number) => Promise<Leitura<Vigencia[]>>;
  gravar: (contaId: number, dia: number, vigenteDesde: string) => Promise<Escrita<Vigencia>>;
  /** Chamado depois de gravar, para a fatura (situação aberta/fechada) ser buscada de novo. */
  aoGravar: () => void;
};

/**
 * Um dia do mês com vigência para o cartão (fechamento ou vencimento): lista as vigências já
 * cadastradas e grava uma nova. Repetir a mesma data só substitui o dia (o servidor é
 * idempotente). A regra de "dia inexistente no mês" é do servidor; a tela só a explica.
 */
export function VigenciaDoCartao({ titulo, explicacao, cartao, listar, gravar, aoGravar }: Props) {
  const { aoSessaoExpirar } = useCasca();
  const buscar = useCallback(() => listar(cartao.conta_id), [listar, cartao.conta_id]);
  const { estado, recarregar, atualizar } = useCarga(buscar);
  const form = useErroDeFormulario();
  const [dia, setDia] = useState("");
  const [desde, setDesde] = useState(hojeEmSaoPaulo);
  const [enviando, setEnviando] = useState(false);
  const [salvo, setSalvo] = useState<string | null>(null);

  async function enviar(evento: FormEvent<HTMLFormElement>) {
    evento.preventDefault();
    form.limpar();
    setSalvo(null);
    const diaNumero = lerInteiro(dia, 1, 31);
    if (diaNumero === null) {
      form.mostrar("dia", "O dia vai de 1 a 31.");
      return;
    }
    if (desde === "") {
      form.mostrar("desde", "Escolha a partir de que data este dia vale.");
      return;
    }
    setEnviando(true);
    const r = await gravar(cartao.conta_id, diaNumero, desde);
    setEnviando(false);
    if (r.tipo === "ok") {
      setSalvo(`${titulo} salvo: dia ${r.dados.dia}, a partir de ${formatarData(r.dados.vigente_desde)}.`);
      atualizar();
      aoGravar();
    } else if (r.tipo === "sessao_expirada") {
      aoSessaoExpirar();
    } else {
      form.mostrarGeral(
        textoDaFalha(r, {
          desatualizado: "Os dados mudaram. Confira a lista e tente de novo.",
          conflito: "Este valor entra em conflito com outro já cadastrado.",
        }),
      );
    }
  }

  return (
    <Cartao titulo={`${titulo} do cartão`}>
      <p className="texto-suave">{explicacao}</p>
      <Estado
        estado={estado}
        aoTentarDeNovo={recarregar}
        textoCarregando="Carregando…"
        textoErro={`Não foi possível carregar o ${titulo.toLowerCase()}.`}
      >
        {(vigencias) =>
          vigencias.length === 0 ? (
            <p className="texto-suave">Nenhum dia cadastrado ainda.</p>
          ) : (
            <ul className="lista" aria-label={`Histórico: ${titulo}`}>
              {[...vigencias].reverse().map((v) => (
                <li key={v.vigente_desde} className="lista-item">
                  Dia {v.dia}, a partir de {formatarData(v.vigente_desde)}
                </li>
              ))}
            </ul>
          )
        }
      </Estado>
      <form
        className="formulario"
        aria-label={`Novo ${titulo.toLowerCase()}`}
        onSubmit={(e) => void enviar(e)}
      >
        <div className="linha-campos">
          <div className="campo">
            <label htmlFor={form.marcar("dia").id}>Dia do mês</label>
            <input
              {...form.marcar("dia")}
              inputMode="numeric"
              autoComplete="off"
              placeholder="10"
              value={dia}
              onChange={(e) => {
                setDia(e.target.value);
                setSalvo(null);
                form.limpar();
              }}
            />
            <span className="ajuda">
              De 1 a 31. Se o mês não tem esse dia, vale o último dia do mês (31 em abril vira 30).
            </span>
          </div>
          <div className="campo">
            <label htmlFor={form.marcar("desde").id}>Vigente desde</label>
            <input
              {...form.marcar("desde")}
              type="date"
              min="2000-01-01"
              value={desde}
              onChange={(e) => {
                setDesde(e.target.value);
                setSalvo(null);
                form.limpar();
              }}
            />
            <span className="ajuda">O dia vale a partir desta data. As anteriores ficam como estão.</span>
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
            {enviando ? "Salvando…" : `Salvar ${titulo.toLowerCase()}`}
          </button>
        </div>
      </form>
    </Cartao>
  );
}
