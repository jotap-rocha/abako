import { type FormEvent, useCallback, useEffect, useRef, useState } from "react";

import { criarCartao, criarLinha, listarLinhas } from "../api/cartoes";
import type { ContaSaida, LinhaSaida } from "../api/gerado";
import { gravarFechamento } from "../api/vigencias";
import { formatarData, primeiroDiaDoMesAtual } from "../datas";
import { formatarMoeda, lerValorDigitado } from "../dinheiro";
import { lerInteiro } from "../inteiro";
import { useCasca } from "../layout/useCasca";
import { Estado } from "../leitura/pecas";
import { useCarga } from "../leitura/useCarga";
import { Cartao } from "../ui/componentes";
import { textoDaFalha } from "../ui/falhas";
import { ErroDoFormulario, type MarcaDeCampo, useErroDeFormulario } from "../ui/formulario";

type Modo = "nova" | "existente";

type Props = {
  /** Depois de criar o cartão: a lista de cartões é buscada de novo (sem desmontar a tela). */
  aoCriar: (contaId: number) => void;
  /** "Cartão criado, falta o fechamento": leva o usuário ao `ConfigCartao` daquele cartão. */
  aoAbrirConfig: (contaId: number) => void;
  /** Cartão que acabou de ganhar fechamento pelo ConfigCartao (some o aviso "falta o fechamento"). */
  cartaoComFechamento?: number | null;
};

type SemFechamento = { cartao: ContaSaida; motivo: string };

/**
 * Seção "Novo cartão". Não há endpoint que crie tudo de uma vez, então as chamadas saem em ordem
 * (linha, cartão, fechamento) e uma falha no meio é tratada na tela: a linha já criada é
 * reaproveitada na nova tentativa, e o cartão criado sem fechamento vira um aviso com atalho.
 * O limite é texto (o banco confere o formato); nenhuma conta é feita aqui (ADR 015, 055).
 */
export function NovoCartao({ aoCriar, aoAbrirConfig, cartaoComFechamento = null }: Props) {
  const { aoSessaoExpirar } = useCasca();
  const form = useErroDeFormulario();
  const [modo, setModo] = useState<Modo>("nova");
  const [nomeLinha, setNomeLinha] = useState("");
  const [limite, setLimite] = useState("");
  const [linhaId, setLinhaId] = useState("");
  const [nomeCartao, setNomeCartao] = useState("");
  const [dia, setDia] = useState("");
  const [desde, setDesde] = useState(primeiroDiaDoMesAtual);
  const [enviando, setEnviando] = useState(false);
  // Linha criada nesta tentativa: se o cartão falhar, a nova tentativa reaproveita esta linha.
  const [linhaCriada, setLinhaCriada] = useState<LinhaSaida | null>(null);
  const [semFechamento, setSemFechamento] = useState<SemFechamento | null>(null);
  const [sucesso, setSucesso] = useState<string | null>(null);
  // Quantas linhas existem no modo "linha existente" (nulo = ainda não carregou ou deu erro).
  const [qtdLinhas, setQtdLinhas] = useState<number | null>(null);
  // Guarda contra duplo clique: o segundo envio é ignorado enquanto o primeiro está em voo.
  const emVoo = useRef(false);

  useEffect(() => {
    if (semFechamento !== null && cartaoComFechamento === semFechamento.cartao.conta_id) {
      setSemFechamento(null);
    }
  }, [cartaoComFechamento, semFechamento]);

  function mudou() {
    form.limpar();
    setSucesso(null);
  }

  function limparCampos() {
    setNomeLinha("");
    setLimite("");
    setLinhaId("");
    setNomeCartao("");
    setDia("");
    setDesde(primeiroDiaDoMesAtual());
    setLinhaCriada(null);
  }

  async function enviar(evento: FormEvent<HTMLFormElement>) {
    evento.preventDefault();
    if (emVoo.current) return;
    form.limpar();
    setSucesso(null);
    setSemFechamento(null);

    const nomeC = nomeCartao.trim();
    let limiteTexto: string | null = null;
    if (modo === "nova" && linhaCriada === null) {
      if (nomeLinha.trim() === "") {
        form.mostrar("nome_linha", "Dê um nome à linha de crédito.");
        return;
      }
      limiteTexto = lerValorDigitado(limite);
      if (limiteTexto === null || limiteTexto.startsWith("-")) {
        form.mostrar("limite", "Informe o limite como valor positivo, por exemplo 5000,00.");
        return;
      }
    }
    if (modo === "existente" && linhaId === "") {
      if (qtdLinhas !== null && qtdLinhas > 0) {
        form.mostrar("linha", "Escolha a linha de crédito do cartão.");
      } else {
        // Sem lista na tela não há campo para marcar: o erro vai para o formulário.
        form.mostrarGeral("Não há linha de crédito para escolher. Crie uma nova linha.");
      }
      return;
    }
    if (nomeC === "") {
      form.mostrar("nome_cartao", "Dê um nome ao cartão.");
      return;
    }
    let diaNumero: number | null = null;
    if (dia.trim() !== "") {
      diaNumero = lerInteiro(dia, 1, 31);
      if (diaNumero === null) {
        form.mostrar("dia", "O dia de fechamento vai de 1 a 31.");
        return;
      }
      if (desde === "") {
        form.mostrar("desde", "Escolha a partir de que data o fechamento vale.");
        return;
      }
    }

    emVoo.current = true;
    setEnviando(true);
    try {
      // 1) Linha (só se for nova; uma linha criada numa tentativa anterior é reaproveitada).
      let idDaLinha: number;
      if (modo === "existente") {
        // `+` troca o texto do id (não é dinheiro) por número; ids são inteiros pequenos.
        idDaLinha = +linhaId;
      } else if (linhaCriada !== null) {
        idDaLinha = linhaCriada.linha_id;
      } else {
        const rl = await criarLinha(nomeLinha.trim(), limiteTexto ?? "");
        if (rl.tipo === "sessao_expirada") return aoSessaoExpirar();
        if (rl.tipo !== "ok") {
          if (rl.tipo === "conflito") {
            form.mostrar("nome_linha", "Já existe uma linha de crédito com este nome.");
          } else {
            form.mostrarGeral(
              textoDaFalha(rl, {
                desatualizado: "Os dados mudaram. Confira a tela e tente de novo.",
                conflito: "Já existe uma linha de crédito com este nome.",
              }),
            );
          }
          return;
        }
        setLinhaCriada(rl.dados);
        idDaLinha = rl.dados.linha_id;
      }

      // 2) Cartão ligado à linha.
      const rc = await criarCartao(nomeC, idDaLinha);
      if (rc.tipo === "sessao_expirada") return aoSessaoExpirar();
      if (rc.tipo !== "ok") {
        const aviso =
          modo === "nova"
            ? " A linha de crédito já foi criada e será reaproveitada na próxima tentativa."
            : "";
        if (rc.tipo === "conflito") {
          form.mostrar("nome_cartao", `Já existe uma conta com este nome.${aviso}`);
        } else {
          form.mostrarGeral(
            `${textoDaFalha(rc, {
              desatualizado: "Os dados mudaram. Confira a tela e tente de novo.",
              conflito: "Já existe uma conta com este nome.",
            })}${aviso}`,
          );
        }
        return;
      }
      const cartao = rc.dados;
      aoCriar(cartao.conta_id);

      // 3) Fechamento (opcional).
      if (diaNumero === null) {
        limparCampos();
        setSucesso(
          `Cartão "${cartao.nome}" criado sem fechamento. Sem fechamento, a compra no crédito será recusada.`,
        );
        return;
      }
      const rf = await gravarFechamento(cartao.conta_id, diaNumero, desde);
      limparCampos();
      if (rf.tipo === "ok") {
        setSucesso(
          `Cartão "${cartao.nome}" criado, com fechamento no dia ${rf.dados.dia} a partir de ${formatarData(rf.dados.vigente_desde)}.`,
        );
        return;
      }
      if (rf.tipo === "sessao_expirada") return aoSessaoExpirar();
      setSemFechamento({
        cartao,
        motivo: textoDaFalha(rf, {
          desatualizado: "Os dados mudaram.",
          conflito: "O fechamento entra em conflito com outro já cadastrado.",
        }),
      });
    } finally {
      emVoo.current = false;
      setEnviando(false);
    }
  }

  return (
    <Cartao titulo="Novo cartão">
      <p className="texto-suave">
        Todo cartão fica ligado a uma linha de crédito, que é o limite. Dois cartões da mesma
        linha compartilham o limite: a compra em um deles reduz o disponível dos dois.
      </p>
      <p className="texto-suave">
        Dívida inicial: começamos do zero. Parcelas antigas ainda em aberto precisam ser lançadas
        uma a uma.
      </p>
      <form className="formulario" aria-label="Novo cartão" onSubmit={(e) => void enviar(e)}>
        <fieldset className="campo">
          <legend>Linha de crédito</legend>
          <label>
            <input
              type="radio"
              name="modo-linha"
              checked={modo === "nova"}
              disabled={enviando}
              onChange={() => {
                setModo("nova");
                mudou();
              }}
            />{" "}
            Criar uma linha nova
          </label>{" "}
          <label>
            <input
              type="radio"
              name="modo-linha"
              checked={modo === "existente"}
              disabled={enviando || linhaCriada !== null}
              onChange={() => {
                setModo("existente");
                setQtdLinhas(null);
                mudou();
              }}
            />{" "}
            Usar uma linha que já existe
          </label>
        </fieldset>

        {modo === "nova" ? (
          <div className="linha-campos">
            <div className="campo">
              <label htmlFor={form.marcar("nome_linha").id}>Nome da linha</label>
              <input
                {...form.marcar("nome_linha")}
                autoComplete="off"
                maxLength={80}
                value={nomeLinha}
                disabled={linhaCriada !== null}
                onChange={(e) => {
                  setNomeLinha(e.target.value);
                  mudou();
                }}
              />
            </div>
            <div className="campo">
              <label htmlFor={form.marcar("limite").id}>Limite (R$)</label>
              <input
                {...form.marcar("limite")}
                inputMode="decimal"
                autoComplete="off"
                placeholder="5000,00"
                value={limite}
                disabled={linhaCriada !== null}
                onChange={(e) => {
                  setLimite(e.target.value);
                  mudou();
                }}
              />
            </div>
          </div>
        ) : (
          <EscolherLinha
            aoCarregar={setQtdLinhas}
            marca={form.marcar("linha")}
            valor={linhaId}
            aoMudar={(v) => {
              setLinhaId(v);
              mudou();
            }}
          />
        )}
        {linhaCriada !== null && (
          <p className="texto-suave" role="status">
            A linha de crédito "{linhaCriada.nome}" já foi criada e será reaproveitada.{" "}
            <button
              type="button"
              className="botao botao-secundario"
              disabled={enviando}
              onClick={() => {
                setLinhaCriada(null);
                mudou();
              }}
            >
              Usar outra linha
            </button>
          </p>
        )}

        <div className="campo">
          <label htmlFor={form.marcar("nome_cartao").id}>Nome do cartão</label>
          <input
            {...form.marcar("nome_cartao")}
            autoComplete="off"
            maxLength={80}
            value={nomeCartao}
            onChange={(e) => {
              setNomeCartao(e.target.value);
              mudou();
            }}
          />
        </div>

        <div className="linha-campos">
          <div className="campo">
            <label htmlFor={form.marcar("dia").id}>Dia de fechamento (opcional)</label>
            <input
              {...form.marcar("dia")}
              inputMode="numeric"
              autoComplete="off"
              placeholder="10"
              value={dia}
              onChange={(e) => {
                setDia(e.target.value);
                mudou();
              }}
            />
            <span className="ajuda">
              De 1 a 31. Sem fechamento, a compra no crédito será recusada.
            </span>
          </div>
          <div className="campo">
            <label htmlFor={form.marcar("desde").id}>Vale a partir de</label>
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
            <span className="ajuda">Compras anteriores a esta data são recusadas.</span>
          </div>
        </div>

        <ErroDoFormulario id={form.idErro} texto={form.erro?.mensagem ?? null} />
        {sucesso !== null && (
          <p className="resultado" role="status">
            {sucesso}
          </p>
        )}
        {semFechamento !== null && (
          <div className="estado estado-erro" role="alert">
            <p>
              Cartão "{semFechamento.cartao.nome}" criado, falta o fechamento: {semFechamento.motivo}
            </p>
            <button
              type="button"
              className="botao botao-secundario"
              onClick={() => aoAbrirConfig(semFechamento.cartao.conta_id)}
            >
              Cadastrar o fechamento
            </button>
          </div>
        )}
        <div className="acoes">
          <button
            type="submit"
            className="botao botao-primario"
            disabled={enviando || (modo === "existente" && qtdLinhas === 0)}
          >
            {enviando ? "Criando…" : "Criar cartão"}
          </button>
        </div>
      </form>
    </Cartao>
  );
}

type EscolherProps = {
  marca: MarcaDeCampo;
  valor: string;
  aoMudar: (v: string) => void;
  /** Quantidade de linhas depois da busca (nulo = ainda não carregou ou erro). */
  aoCarregar: (quantidade: number | null) => void;
};

/** Lista as linhas existentes (buscadas ao abrir esta opção, para nunca estarem velhas). */
function EscolherLinha({ marca, valor, aoMudar, aoCarregar }: EscolherProps) {
  const buscar = useCallback(() => listarLinhas(), []);
  const { estado, recarregar } = useCarga(buscar);
  useEffect(() => {
    aoCarregar(estado.tipo === "ok" ? estado.dados.length : null);
  }, [estado, aoCarregar]);
  return (
    <Estado
      estado={estado}
      aoTentarDeNovo={recarregar}
      textoCarregando="Carregando linhas de crédito…"
      textoErro="Não foi possível carregar as linhas de crédito."
    >
      {(linhas) =>
        linhas.length === 0 ? (
          <p className="texto-suave">Nenhuma linha cadastrada ainda. Crie uma nova linha.</p>
        ) : (
          <div className="campo">
            <label htmlFor={marca.id}>Linha de crédito do cartão</label>
            <select
              {...marca}
              value={valor}
              onChange={(e) => aoMudar(e.target.value)}
            >
              <option value="">Escolha…</option>
              {linhas.map((l) => (
                <option key={l.linha_id} value={l.linha_id}>
                  {l.nome} (limite {formatarMoeda(l.limite)})
                </option>
              ))}
            </select>
            <span className="ajuda">
              O novo cartão compartilha o limite desta linha com os outros cartões dela.
            </span>
          </div>
        )
      }
    </Estado>
  );
}
