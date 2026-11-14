import { type FormEvent, useState } from "react";
import { Link } from "react-router";

import type { ContaSaida } from "../api/gerado";
import { gravarParametroVale } from "../api/vale";
import { nomeDoMes } from "../datas";
import { lerValorDigitado } from "../dinheiro";
import { useCasca } from "../layout/useCasca";
import { rotuloDoDestino } from "../leitura/rotulos";
import { textoDaFalha } from "../ui/falhas";
import { ErroDoFormulario, useErroDeFormulario } from "../ui/formulario";

const DESTINOS = ["trabalho", "pessoal", "nenhum"] as const;
/** Sugestão de base de trabalho (ADR 052); só vale depois de gravada. */
const BASE_SUGERIDA = "200,00";

const TEXTOS = {
  desatualizado: "Os dados mudaram. Confira e tente de novo.",
  conflito: "Este valor entra em conflito com outro já cadastrado.",
};

type Inicial = { contaId: number | null; base: string | null; destino: string };

/**
 * Marca qual conta de benefício é o VR, a base de trabalho e o destino padrão da sobra, a partir
 * de um mês ("vigente desde"). A vigência é sempre o dia 1 do mês: um mês antigo continua com os
 * valores que valiam nele. As regras (conta de benefício, despesa sem bolso) são do banco; a
 * mensagem dele aparece como veio.
 */
export function ParametroVale({
  contas,
  mes,
  inicial,
  aoGravar,
}: {
  contas: ContaSaida[];
  mes: string;
  inicial: Inicial | null;
  aoGravar: () => void;
}) {
  const { aoSessaoExpirar } = useCasca();
  const form = useErroDeFormulario();
  const [contaId, setContaId] = useState<number | null>(inicial?.contaId ?? null);
  const [base, setBase] = useState(
    inicial?.base == null ? BASE_SUGERIDA : inicial.base.replace(".", ","),
  );
  const [destino, setDestino] = useState<string>(inicial?.destino ?? "nenhum");
  const [desde, setDesde] = useState(mes);
  const [enviando, setEnviando] = useState(false);
  const [salvo, setSalvo] = useState<string | null>(null);
  // Marcação recusada pelo banco (422): além da mensagem dele, a orientação do que fazer.
  const [recusada, setRecusada] = useState(false);

  async function enviar(evento: FormEvent<HTMLFormElement>) {
    evento.preventDefault();
    form.limpar();
    setSalvo(null);
    setRecusada(false);
    if (contaId === null) {
      form.mostrar("conta", "Escolha a conta do vale-refeição.");
      return;
    }
    const baseTexto = lerValorDigitado(base);
    if (baseTexto === null || baseTexto.startsWith("-")) {
      form.mostrar("base", "Valor não reconhecido. Escreva, sem sinal de menos, por exemplo 200,00.");
      return;
    }
    if (!/^\d{4}-\d{2}$/.test(desde)) {
      form.mostrar("desde", "Escolha a partir de que mês estes valores valem.");
      return;
    }
    setEnviando(true);
    const r = await gravarParametroVale({
      contaId,
      baseTrabalho: baseTexto,
      destinoPadrao: destino,
      vigenteDesde: `${desde}-01`,
    });
    setEnviando(false);
    if (r.tipo === "ok") {
      setSalvo(`VR marcado a partir de ${nomeDoMes(desde)}.`);
      aoGravar();
    } else if (r.tipo === "sessao_expirada") {
      aoSessaoExpirar();
    } else {
      form.mostrarGeral(textoDaFalha(r, TEXTOS));
      // Quem recusa é o banco; a tela só explica o caminho quando a recusa é por regra (422).
      setRecusada(r.tipo === "invalido");
    }
  }

  function mudou() {
    setSalvo(null);
    setRecusada(false);
    form.limpar();
  }

  if (contas.length === 0) {
    return (
      <p className="texto-suave">
        Nenhuma conta do tipo Benefício ainda. Crie uma em Contas, com o tipo Benefício, e volte
        aqui.
      </p>
    );
  }

  return (
    <form className="formulario" aria-label="Marcar a conta do VR" onSubmit={(e) => void enviar(e)}>
      <div className="linha-campos">
        <div className="campo">
          <label htmlFor={form.marcar("conta").id}>Conta do VR</label>
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
        </div>
        <div className="campo">
          <label htmlFor={form.marcar("base").id}>Base de trabalho (R$)</label>
          <input
            {...form.marcar("base")}
            inputMode="decimal"
            autoComplete="off"
            value={base}
            onChange={(e) => {
              setBase(e.target.value);
              mudou();
            }}
          />
          <span className="ajuda">Quanto do crédito é reservado ao bolso de trabalho.</span>
        </div>
      </div>
      <div className="linha-campos">
        <div className="campo">
          <label htmlFor={form.marcar("destino").id}>Destino padrão da sobra</label>
          <select
            {...form.marcar("destino")}
            value={destino}
            onChange={(e) => {
              setDestino(DESTINOS.find((d) => d === e.target.value) ?? "nenhum");
              mudou();
            }}
          >
            {DESTINOS.map((d) => (
              <option key={d} value={d}>
                {rotuloDoDestino(d)}
              </option>
            ))}
          </select>
          <span className="ajuda">Só pré-seleciona a decisão; sem decisão, a sobra não passa.</span>
        </div>
        <div className="campo">
          <label htmlFor={form.marcar("desde").id}>Vigente desde (mês)</label>
          <input
            {...form.marcar("desde")}
            type="month"
            value={desde}
            onChange={(e) => {
              setDesde(e.target.value);
              mudou();
            }}
          />
        </div>
      </div>
      <ErroDoFormulario id={form.idErro} texto={form.erro?.mensagem ?? null} />
      {recusada && (
        <p className="texto-suave">
          Se a mensagem fala de despesas sem bolso: abra os lançamentos desta conta, edite cada
          despesa informando o bolso e tente marcar de novo.{" "}
          <Link className="link" to="/lancamentos">
            Abrir os lançamentos
          </Link>
        </p>
      )}
      {salvo !== null && (
        <p className="resultado" role="status">
          {salvo}
        </p>
      )}
      <div className="acoes">
        <button type="submit" className="botao botao-primario" disabled={enviando}>
          {enviando ? "Salvando…" : "Salvar marcação do VR"}
        </button>
      </div>
    </form>
  );
}
