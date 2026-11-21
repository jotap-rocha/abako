import { type FormEvent, useCallback, useRef, useState } from "react";

import { editarLinha, listarLinhas } from "../api/cartoes";
import type { Leitura } from "../api/base";
import type { LinhaSaida } from "../api/gerado";
import { lerValorDigitado } from "../dinheiro";
import { useCasca } from "../layout/useCasca";
import { Estado } from "../leitura/pecas";
import { useCarga } from "../leitura/useCarga";
import { Cartao } from "../ui/componentes";
import { textoDaFalha } from "../ui/falhas";
import { ErroDoFormulario, useErroDeFormulario } from "../ui/formulario";

type Props = {
  linhaId: number;
  /** Depois de salvar: o limite exibido na tela é buscado de novo. */
  aoSalvar: () => void;
};

/**
 * Nome e limite da linha de crédito do cartão. As linhas só são buscadas quando o usuário pede
 * para editar. Editar cria uma nova versão; o `versao` lido volta no envio (409 se mudou antes).
 * Não há vigência por data: o limite novo vale para tudo, inclusive o passado (ADR 055).
 */
export function EditarLinha({ linhaId, aoSalvar }: Props) {
  const [aberto, setAberto] = useState(false);
  const [salvo, setSalvo] = useState<string | null>(null);
  return (
    <Cartao titulo="Linha de crédito">
      <p className="texto-suave">
        O limite novo vale para tudo, inclusive o passado: não há data de início para o limite.
        Vale também para todos os cartões que compartilham esta linha.
      </p>
      {salvo !== null && (
        <p className="resultado" role="status">
          {salvo}
        </p>
      )}
      {aberto ? (
        <Formulario
          linhaId={linhaId}
          aoSalvar={(linha) => {
            setAberto(false);
            setSalvo(`Linha "${linha.nome}" salva.`);
            aoSalvar();
          }}
          aoCancelar={() => setAberto(false)}
        />
      ) : (
        <div className="acoes">
          <button
            type="button"
            className="botao botao-secundario"
            onClick={() => {
              setSalvo(null);
              setAberto(true);
            }}
          >
            Editar nome e limite da linha
          </button>
        </div>
      )}
    </Cartao>
  );
}

type FormProps = { linhaId: number; aoSalvar: (l: LinhaSaida) => void; aoCancelar: () => void };

function Formulario({ linhaId, aoSalvar, aoCancelar }: FormProps) {
  const buscar = useCallback(async (): Promise<Leitura<LinhaSaida>> => {
    const r = await listarLinhas();
    if (r.tipo !== "ok") return r;
    const linha = r.dados.find((l) => l.linha_id === linhaId);
    return linha === undefined ? { tipo: "nao_encontrado" } : { tipo: "ok", dados: linha };
  }, [linhaId]);
  const { estado, recarregar } = useCarga(buscar);
  // Recarregar troca a tela por "carregando" e desmonta os campos: o aviso fica aqui, acima deles.
  const [aviso, setAviso] = useState<string | null>(null);
  return (
    <Estado
      estado={estado}
      aoTentarDeNovo={recarregar}
      textoCarregando="Carregando a linha…"
      textoErro="Não foi possível carregar a linha."
    >
      {(linha) => (
        <Campos
          linha={linha}
          aviso={aviso}
          aoLimparAviso={() => setAviso(null)}
          aoSalvar={aoSalvar}
          aoCancelar={aoCancelar}
          aoDesatualizado={() => {
            setAviso(
              "A linha mudou desde a leitura. Os dados foram carregados de novo; confira e salve outra vez.",
            );
            recarregar();
          }}
        />
      )}
    </Estado>
  );
}

type CamposProps = {
  linha: LinhaSaida;
  aoSalvar: (l: LinhaSaida) => void;
  aoCancelar: () => void;
  aviso: string | null;
  aoLimparAviso: () => void;
  aoDesatualizado: () => void;
};

function Campos({ linha, aoSalvar, aoCancelar, aviso, aoLimparAviso, aoDesatualizado }: CamposProps) {
  const { aoSessaoExpirar } = useCasca();
  const form = useErroDeFormulario();
  const [nome, setNome] = useState(linha.nome);
  const [limite, setLimite] = useState(linha.limite);
  const [enviando, setEnviando] = useState(false);
  const emVoo = useRef(false);

  async function enviar(evento: FormEvent<HTMLFormElement>) {
    evento.preventDefault();
    if (emVoo.current) return;
    form.limpar();
    aoLimparAviso();
    if (nome.trim() === "") {
      form.mostrar("nome", "Dê um nome à linha de crédito.");
      return;
    }
    const limiteTexto = lerValorDigitado(limite);
    if (limiteTexto === null || limiteTexto.startsWith("-")) {
      form.mostrar("limite", "Informe o limite como valor positivo, por exemplo 5000,00.");
      return;
    }
    emVoo.current = true;
    setEnviando(true);
    // A versão enviada é a que a tela leu ao abrir a edição (INV-29).
    const r = await editarLinha(linha.linha_id, linha.versao, nome.trim(), limiteTexto);
    emVoo.current = false;
    setEnviando(false);
    if (r.tipo === "ok") {
      aoSalvar(r.dados);
    } else if (r.tipo === "sessao_expirada") {
      aoSessaoExpirar();
    } else if (r.tipo === "desatualizado") {
      aoDesatualizado();
    } else if (r.tipo === "conflito") {
      form.mostrar("nome", "Já existe uma linha de crédito com este nome.");
    } else {
      form.mostrarGeral(
        textoDaFalha(r, {
          desatualizado: "A linha mudou desde a leitura.",
          conflito: "Já existe uma linha de crédito com este nome.",
        }),
      );
    }
  }

  return (
    <form className="formulario" aria-label="Editar linha de crédito" onSubmit={(e) => void enviar(e)}>
      <div className="linha-campos">
        <div className="campo">
          <label htmlFor={form.marcar("nome").id}>Nome da linha</label>
          <input
            {...form.marcar("nome")}
            autoComplete="off"
            maxLength={80}
            value={nome}
            onChange={(e) => {
              setNome(e.target.value);
              form.limpar();
              aoLimparAviso();
            }}
          />
        </div>
        <div className="campo">
          <label htmlFor={form.marcar("limite").id}>Limite (R$)</label>
          <input
            {...form.marcar("limite")}
            inputMode="decimal"
            autoComplete="off"
            value={limite}
            onChange={(e) => {
              setLimite(e.target.value);
              form.limpar();
              aoLimparAviso();
            }}
          />
        </div>
      </div>
      <ErroDoFormulario id={form.idErro} texto={form.erro?.mensagem ?? aviso} />
      <div className="acoes">
        <button type="submit" className="botao botao-primario" disabled={enviando}>
          {enviando ? "Salvando…" : "Salvar linha"}
        </button>
        <button type="button" className="botao botao-secundario" onClick={aoCancelar}>
          Cancelar
        </button>
      </div>
    </form>
  );
}
