import { type FormEvent, useState } from "react";

import type { HorizonteSaida, ParametroSaida } from "../api/gerado";
import {
  gravarHorizonte,
  gravarParametrosReserva,
  listarHorizontes,
  listarParametrosReserva,
} from "../api/vigencias";
import { formatarData, hojeEmSaoPaulo } from "../datas";
import { formatarMoeda, lerValorDigitado } from "../dinheiro";
import { lerInteiro } from "../inteiro";
import { useCasca } from "../layout/useCasca";
import { Estado } from "../leitura/pecas";
import { useCarga } from "../leitura/useCarga";
import { Cartao, Pagina } from "../ui/componentes";
import { textoDaFalha } from "../ui/falhas";
import { ErroDoFormulario, useErroDeFormulario } from "../ui/formulario";

const TEXTOS = {
  desatualizado: "Os dados mudaram. Confira o histórico e tente de novo.",
  conflito: "Este valor entra em conflito com outro já cadastrado.",
};

/**
 * Parâmetros: a meta da reserva e o horizonte do R2. Cada gravação vale a partir de uma data
 * ("vigente desde"), e o histórico de vigências fica visível. Cobertura, nível, aporte e sobra
 * são calculados pelo servidor com o parâmetro vigente; a tela só grava e lista.
 */
export function Parametros() {
  return (
    <Pagina
      titulo="Parâmetros"
      descricao="Metas e janelas que o abako usa nos cálculos. Cada mudança vale a partir de uma data; o que veio antes não muda."
    >
      <ReservaParametros />
      <HorizonteR2 />
    </Pagina>
  );
}

// ------------------------------------------------------------------ reserva

function ReservaParametros() {
  const { estado, recarregar, atualizar } = useCarga(listarParametrosReserva);
  return (
    <Cartao titulo="Meta da reserva">
      <p className="texto-suave">
        Quantos meses do gasto essencial a reserva deve cobrir. Com a meta e o gasto essencial, o
        abako mostra a cobertura em meses e o nível da reserva (crítica abaixo de 50% da meta,
        saudável a partir de 100%). A data-alvo, se houver, define o aporte mensal sugerido.
      </p>
      <Estado
        estado={estado}
        aoTentarDeNovo={recarregar}
        textoCarregando="Carregando a meta da reserva…"
        textoErro="Não foi possível carregar a meta da reserva."
      >
        {(lista) => (
          <>
            {lista.length === 0 ? (
              <p className="texto-suave">A reserva ainda não está configurada.</p>
            ) : (
              <ul className="lista" aria-label="Histórico da meta da reserva">
                {[...lista].reverse().map((p) => (
                  <li key={p.vigente_desde} className="lista-item lista-item-coluna">
                    <span className="conta-nome">A partir de {formatarData(p.vigente_desde)}</span>
                    <span className="texto-suave">
                      {p.meses} meses · gasto essencial {formatarMoeda(p.gasto_essencial)} ·{" "}
                      {p.data_alvo === null
                        ? "sem data-alvo"
                        : `alvo em ${formatarData(p.data_alvo)}`}
                    </span>
                  </li>
                ))}
              </ul>
            )}
            <FormularioReserva ultimo={lista[lista.length - 1]} aoGravar={atualizar} />
          </>
        )}
      </Estado>
    </Cartao>
  );
}

function FormularioReserva({
  ultimo,
  aoGravar,
}: {
  ultimo: ParametroSaida | undefined;
  aoGravar: () => void;
}) {
  const { aoSessaoExpirar } = useCasca();
  const form = useErroDeFormulario();
  // Começa com a última vigência cadastrada, para mudar só o que mudou.
  const [meses, setMeses] = useState(ultimo === undefined ? "" : String(ultimo.meses));
  const [gasto, setGasto] = useState(
    ultimo === undefined ? "" : ultimo.gasto_essencial.replace(".", ","),
  );
  const [alvo, setAlvo] = useState(ultimo?.data_alvo ?? "");
  const [desde, setDesde] = useState(hojeEmSaoPaulo);
  const [enviando, setEnviando] = useState(false);
  const [salvo, setSalvo] = useState<string | null>(null);

  async function enviar(evento: FormEvent<HTMLFormElement>) {
    evento.preventDefault();
    form.limpar();
    setSalvo(null);
    const mesesNumero = lerInteiro(meses, 1, 120);
    if (mesesNumero === null) {
      form.mostrar("meses", "A meta vai de 1 a 120 meses.");
      return;
    }
    const gastoTexto = lerValorDigitado(gasto);
    if (gastoTexto === null || gastoTexto.startsWith("-")) {
      form.mostrar("gasto", "Valor não reconhecido. Escreva, sem sinal de menos, por exemplo 3.500,00.");
      return;
    }
    if (desde === "") {
      form.mostrar("desde", "Escolha a partir de que data estes valores valem.");
      return;
    }
    setEnviando(true);
    const r = await gravarParametrosReserva({
      meses: mesesNumero,
      gastoEssencial: gastoTexto,
      dataAlvo: alvo === "" ? null : alvo,
      vigenteDesde: desde,
    });
    setEnviando(false);
    if (r.tipo === "ok") {
      setSalvo(`Meta salva a partir de ${formatarData(r.dados.vigente_desde)}.`);
      aoGravar();
    } else if (r.tipo === "sessao_expirada") {
      aoSessaoExpirar();
    } else {
      form.mostrarGeral(textoDaFalha(r, TEXTOS));
    }
  }

  function mudou() {
    setSalvo(null);
    form.limpar();
  }

  return (
    <form className="formulario" aria-label="Meta da reserva" onSubmit={(e) => void enviar(e)}>
      <div className="linha-campos">
        <div className="campo">
          <label htmlFor={form.marcar("meses").id}>Meta (meses de gasto essencial)</label>
          <input
            {...form.marcar("meses")}
            inputMode="numeric"
            autoComplete="off"
            placeholder="6"
            value={meses}
            onChange={(e) => {
              setMeses(e.target.value);
              mudou();
            }}
          />
          <span className="ajuda">De 1 a 120.</span>
        </div>
        <div className="campo">
          <label htmlFor={form.marcar("gasto").id}>Gasto essencial por mês (R$)</label>
          <input
            {...form.marcar("gasto")}
            inputMode="decimal"
            autoComplete="off"
            placeholder="3.500,00"
            value={gasto}
            onChange={(e) => {
              setGasto(e.target.value);
              mudou();
            }}
          />
          <span className="ajuda">Moradia, comida, contas básicas. Zero deixa a reserva sem configuração.</span>
        </div>
      </div>
      <div className="linha-campos">
        <div className="campo">
          <label htmlFor={form.marcar("alvo").id}>Data-alvo (opcional)</label>
          <input
            {...form.marcar("alvo")}
            type="date"
            min="2000-01-01"
            value={alvo}
            onChange={(e) => {
              setAlvo(e.target.value);
              mudou();
            }}
          />
          <span className="ajuda">Até quando quer atingir a meta. Vazio = sem prazo.</span>
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
              mudou();
            }}
          />
          <span className="ajuda">Estes valores valem a partir desta data.</span>
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
          {enviando ? "Salvando…" : "Salvar meta da reserva"}
        </button>
      </div>
    </form>
  );
}

// ------------------------------------------------------------------ horizonte do R2

function HorizonteR2() {
  const { estado, recarregar, atualizar } = useCarga(listarHorizontes);
  return (
    <Cartao titulo="Horizonte do R2">
      <p className="texto-suave">
        Quantos dias à frente a sobra do R2 olha: receitas, despesas fixas e faturas que vencem
        dentro desse prazo entram na conta. Mais dias, olhar mais longe.
      </p>
      <Estado
        estado={estado}
        aoTentarDeNovo={recarregar}
        textoCarregando="Carregando o horizonte…"
        textoErro="Não foi possível carregar o horizonte."
      >
        {(lista) => (
          <>
            {lista.length === 0 ? (
              <p className="texto-suave">Nenhum horizonte cadastrado ainda.</p>
            ) : (
              <ul className="lista" aria-label="Histórico do horizonte do R2">
                {[...lista].reverse().map((h: HorizonteSaida) => (
                  <li key={h.vigente_desde} className="lista-item">
                    {h.dias} dias, a partir de {formatarData(h.vigente_desde)}
                  </li>
                ))}
              </ul>
            )}
            <FormularioHorizonte ultimo={lista[lista.length - 1]} aoGravar={atualizar} />
          </>
        )}
      </Estado>
    </Cartao>
  );
}

function FormularioHorizonte({
  ultimo,
  aoGravar,
}: {
  ultimo: HorizonteSaida | undefined;
  aoGravar: () => void;
}) {
  const { aoSessaoExpirar } = useCasca();
  const form = useErroDeFormulario();
  const [dias, setDias] = useState(ultimo === undefined ? "" : String(ultimo.dias));
  const [desde, setDesde] = useState(hojeEmSaoPaulo);
  const [enviando, setEnviando] = useState(false);
  const [salvo, setSalvo] = useState<string | null>(null);

  async function enviar(evento: FormEvent<HTMLFormElement>) {
    evento.preventDefault();
    form.limpar();
    setSalvo(null);
    const diasNumero = lerInteiro(dias, 1, 90);
    if (diasNumero === null) {
      form.mostrar("dias", "O horizonte vai de 1 a 90 dias.");
      return;
    }
    if (desde === "") {
      form.mostrar("desde", "Escolha a partir de que data este horizonte vale.");
      return;
    }
    setEnviando(true);
    const r = await gravarHorizonte(diasNumero, desde);
    setEnviando(false);
    if (r.tipo === "ok") {
      setSalvo(`Horizonte salvo: ${r.dados.dias} dias, a partir de ${formatarData(r.dados.vigente_desde)}.`);
      aoGravar();
    } else if (r.tipo === "sessao_expirada") {
      aoSessaoExpirar();
    } else {
      form.mostrarGeral(textoDaFalha(r, TEXTOS));
    }
  }

  return (
    <form className="formulario" aria-label="Horizonte do R2" onSubmit={(e) => void enviar(e)}>
      <div className="linha-campos">
        <div className="campo">
          <label htmlFor={form.marcar("dias").id}>Dias à frente</label>
          <input
            {...form.marcar("dias")}
            inputMode="numeric"
            autoComplete="off"
            placeholder="10"
            value={dias}
            onChange={(e) => {
              setDias(e.target.value);
              setSalvo(null);
              form.limpar();
            }}
          />
          <span className="ajuda">De 1 a 90.</span>
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
          <span className="ajuda">Este horizonte vale a partir desta data.</span>
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
          {enviando ? "Salvando…" : "Salvar horizonte"}
        </button>
      </div>
    </form>
  );
}
