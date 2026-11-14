import { type FormEvent, useState } from "react";

import type { AReceberSaida, PessoaSaida } from "../api/gerado";
import { type Leitura, listarPessoas } from "../api/leitura";
import { criarPessoa, excluirPessoa, listarAReceber, renomearPessoa } from "../api/pessoas";
import { formatarMoeda } from "../dinheiro";
import { useCasca } from "../layout/useCasca";
import { juntar, useCarga } from "../leitura/useCarga";
import { Estado } from "../leitura/pecas";
import { Cartao, EstadoVazio, Pagina } from "../ui/componentes";
import { ConfirmarExclusao } from "../ui/ConfirmarExclusao";
import { textoDaFalha } from "../ui/falhas";
import { ErroDoFormulario, useErroDeFormulario } from "../ui/formulario";

type Dados = { pessoas: PessoaSaida[]; aReceber: AReceberSaida[] };

async function buscar(): Promise<Leitura<Dados>> {
  const r = await juntar(listarPessoas(), listarAReceber());
  if (r.tipo !== "ok") return r;
  return { tipo: "ok", dados: { pessoas: r.dados[0], aReceber: r.dados[1] } };
}

const TEXTOS = {
  desatualizado:
    "Esta pessoa mudou desde que você a viu (talvez em outra aba). A lista foi atualizada: confira e tente de novo.",
  conflito: "Já existe uma pessoa com esse nome. Escolha outro nome.",
};

/**
 * Pessoas (terceiros que compram no seu cartão) e quanto cada uma ainda deve. Os valores de
 * dívida, repassado, a receber e crédito vêm prontos do servidor (ADR 045): a tela só exibe.
 * O nome da pessoa é mostrado em claro só aqui, na sessão do dono (exceção do ADR 050).
 */
export function Pessoas() {
  const { estado, recarregar, atualizar } = useCarga(buscar);
  return (
    <Pagina
      titulo="Pessoas"
      descricao="Quem compra no seu cartão e quanto ainda deve a você. Cadastre a pessoa aqui para lançar a compra dela ou um repasse."
    >
      <Cartao titulo="Nova pessoa">
        <NovaPessoa aoCriar={atualizar} />
      </Cartao>
      <Estado
        estado={estado}
        aoTentarDeNovo={recarregar}
        textoCarregando="Carregando pessoas…"
        textoErro="Não foi possível carregar as pessoas."
      >
        {({ pessoas, aReceber }) =>
          pessoas.length === 0 ? (
            <EstadoVazio
              titulo="Nenhuma pessoa ainda"
              texto="Cadastre a primeira acima. Depois, em Lançamentos, escolha a pessoa numa compra no cartão ou num repasse."
            />
          ) : (
            <>
              <p className="texto-suave">
                <strong>Dívida</strong> é o total das compras da pessoa no cartão, inclusive as
                parcelas futuras. <strong>Repassado</strong> é o que ela já devolveu.{" "}
                <strong>A receber</strong> é o que falta. <strong>Crédito</strong> aparece quando
                ela repassou mais do que devia e abate compras futuras.
              </p>
              <ul className="lista" aria-label="Pessoas">
                {pessoas.map((p) => (
                  <ItemPessoa
                    key={p.pessoa_id}
                    pessoa={p}
                    valores={aReceber.find((a) => a.pessoa_id === p.pessoa_id)}
                    aoMudar={atualizar}
                  />
                ))}
              </ul>
            </>
          )
        }
      </Estado>
    </Pagina>
  );
}

function NovaPessoa({ aoCriar }: { aoCriar: () => void }) {
  const { aoSessaoExpirar } = useCasca();
  const form = useErroDeFormulario();
  const [nome, setNome] = useState("");
  const [enviando, setEnviando] = useState(false);
  const [salvo, setSalvo] = useState<string | null>(null);

  async function enviar(evento: FormEvent<HTMLFormElement>) {
    evento.preventDefault();
    form.limpar();
    setSalvo(null);
    if (nome.trim() === "") {
      form.mostrar("nome", "Escreva o nome da pessoa.");
      return;
    }
    setEnviando(true);
    const r = await criarPessoa(nome);
    setEnviando(false);
    if (r.tipo === "ok") {
      setNome("");
      setSalvo("Pessoa cadastrada.");
      aoCriar();
    } else if (r.tipo === "sessao_expirada") {
      aoSessaoExpirar();
    } else {
      form.mostrar("nome", textoDaFalha(r, TEXTOS));
    }
  }

  return (
    <form className="formulario" aria-label="Nova pessoa" onSubmit={(e) => void enviar(e)}>
      <div className="campo">
        <label htmlFor={form.marcar("nome").id}>Nome</label>
        <input
          {...form.marcar("nome")}
          maxLength={80}
          autoComplete="off"
          value={nome}
          onChange={(e) => {
            setNome(e.target.value);
            setSalvo(null);
            form.limpar();
          }}
        />
        <span className="ajuda">De 1 a 80 caracteres. Não pode repetir o nome de outra pessoa.</span>
      </div>
      <ErroDoFormulario id={form.idErro} texto={form.erro?.mensagem ?? null} />
      {salvo !== null && (
        <p className="resultado" role="status">
          {salvo}
        </p>
      )}
      <div className="acoes">
        <button type="submit" className="botao botao-primario" disabled={enviando}>
          {enviando ? "Cadastrando…" : "Cadastrar pessoa"}
        </button>
      </div>
    </form>
  );
}

type ItemProps = {
  pessoa: PessoaSaida;
  valores: AReceberSaida | undefined;
  aoMudar: () => void;
};

function ItemPessoa({ pessoa, valores, aoMudar }: ItemProps) {
  const { aoSessaoExpirar } = useCasca();
  // A versão enviada é a que estava na tela quando o usuário abriu a edição/confirmação.
  const [modo, setModo] = useState<
    { tipo: "ver" } | { tipo: "renomear"; lida: PessoaSaida } | { tipo: "excluir"; lida: PessoaSaida }
  >({ tipo: "ver" });
  const form = useErroDeFormulario();
  const [nome, setNome] = useState(pessoa.nome);
  const [enviando, setEnviando] = useState(false);
  const [erroExclusao, setErroExclusao] = useState<string | null>(null);

  function fechar() {
    setModo({ tipo: "ver" });
    form.limpar();
    setErroExclusao(null);
  }

  async function salvarNome(evento: FormEvent<HTMLFormElement>, lida: PessoaSaida) {
    evento.preventDefault();
    form.limpar();
    if (nome.trim() === "") {
      form.mostrar("nome", "Escreva o nome da pessoa.");
      return;
    }
    setEnviando(true);
    const r = await renomearPessoa(lida.pessoa_id, lida.versao, nome);
    setEnviando(false);
    if (r.tipo === "ok") {
      fechar();
      aoMudar();
    } else if (r.tipo === "sessao_expirada") {
      aoSessaoExpirar();
    } else {
      form.mostrar("nome", textoDaFalha(r, TEXTOS));
      if (r.tipo === "desatualizado" || r.tipo === "nao_encontrado") aoMudar();
    }
  }

  async function excluir(lida: PessoaSaida) {
    setErroExclusao(null);
    setEnviando(true);
    const r = await excluirPessoa(lida.pessoa_id, lida.versao);
    setEnviando(false);
    if (r.tipo === "ok") {
      aoMudar();
    } else if (r.tipo === "sessao_expirada") {
      aoSessaoExpirar();
    } else {
      setErroExclusao(textoDaFalha(r, TEXTOS));
      if (r.tipo === "desatualizado" || r.tipo === "nao_encontrado") aoMudar();
    }
  }

  return (
    <li className="lista-item lista-item-coluna">
      <div className="conta-resumo">
        <span className="conta-nome">{pessoa.nome}</span>
      </div>
      {valores === undefined ? (
        <p className="texto-suave">Os valores desta pessoa não vieram do servidor.</p>
      ) : (
        <dl className="resumo">
          <div>
            <dt>Dívida</dt>
            <dd>{formatarMoeda(valores.divida)}</dd>
          </div>
          <div>
            <dt>Repassado</dt>
            <dd>{formatarMoeda(valores.repassado)}</dd>
          </div>
          <div>
            <dt>A receber</dt>
            <dd>{formatarMoeda(valores.a_receber)}</dd>
          </div>
          <div>
            <dt>Crédito da pessoa</dt>
            <dd>{formatarMoeda(valores.credito_da_pessoa)}</dd>
          </div>
        </dl>
      )}
      {modo.tipo === "ver" && (
        <span className="acoes">
          <button
            type="button"
            className="botao botao-secundario"
            aria-label={`Renomear ${pessoa.nome}`}
            onClick={() => {
              setNome(pessoa.nome);
              setModo({ tipo: "renomear", lida: pessoa });
            }}
          >
            Renomear
          </button>
          <button
            type="button"
            className="botao botao-secundario"
            aria-label={`Excluir ${pessoa.nome}`}
            onClick={() => setModo({ tipo: "excluir", lida: pessoa })}
          >
            Excluir
          </button>
        </span>
      )}
      {modo.tipo === "renomear" && (
        <form
          className="formulario"
          aria-label={`Renomear ${pessoa.nome}`}
          onSubmit={(e) => void salvarNome(e, modo.lida)}
        >
          <div className="campo">
            <label htmlFor={form.marcar("nome").id}>Novo nome</label>
            <input
              {...form.marcar("nome")}
              autoFocus
              maxLength={80}
              autoComplete="off"
              value={nome}
              onChange={(e) => {
                setNome(e.target.value);
                form.limpar();
              }}
            />
          </div>
          <ErroDoFormulario id={form.idErro} texto={form.erro?.mensagem ?? null} />
          <div className="acoes">
            <button type="submit" className="botao botao-primario" disabled={enviando}>
              {enviando ? "Salvando…" : "Salvar nome"}
            </button>
            <button type="button" className="botao botao-secundario" onClick={fechar}>
              Cancelar
            </button>
          </div>
        </form>
      )}
      {modo.tipo === "excluir" && (
        <ConfirmarExclusao
          texto={`Excluir ${pessoa.nome}? O histórico fica guardado. Se houver compra ou repasse vigente dela, o servidor recusa.`}
          enviando={enviando}
          erro={erroExclusao}
          aoConfirmar={() => void excluir(modo.lida)}
          aoCancelar={fechar}
        />
      )}
    </li>
  );
}
