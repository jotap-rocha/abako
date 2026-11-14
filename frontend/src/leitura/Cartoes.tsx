import { useCallback, useState } from "react";

import type { ContaSaida, FaturaSaida, ItemFaturaSaida, LimiteSaida, PessoaSaida } from "../api/gerado";
import { type Leitura, listarContas, listarPessoas, obterFatura, obterLimite } from "../api/leitura";
import { formatarData, mesAtual } from "../datas";
import { formatarMoeda } from "../dinheiro";
import { Cartao, EstadoVazio, Pagina } from "../ui/componentes";
import { Glossario, Termo } from "./Glossario";
import { Estado, NavegadorMes } from "./pecas";
import { juntar, useCarga } from "./useCarga";

type Dados = { cartoes: ContaSaida[]; pessoas: PessoaSaida[] };

async function buscarCartoes(): Promise<Leitura<Dados>> {
  const resultado = await juntar(listarContas(), listarPessoas());
  if (resultado.tipo !== "ok") return resultado;
  const [contas, pessoas] = resultado.dados;
  // Cartão é uma conta do tipo "dívida" (a linha de crédito, com o limite, fica ligada a ela).
  return { tipo: "ok", dados: { cartoes: contas.filter((c) => c.tipo === "divida"), pessoas } };
}

/**
 * Cartões e faturas. A fatura (total, própria, terceiros, itens), o limite e a situação
 * aberta/fechada vêm prontos da API; a tela só escolhe o cartão e o mês e exibe (ADR 015).
 */
export function Cartoes() {
  const { estado, recarregar } = useCarga(buscarCartoes);
  const [escolhido, setEscolhido] = useState<string | null>(null);
  const [competencia, setCompetencia] = useState(mesAtual);

  return (
    <Pagina
      titulo="Cartões"
      descricao="Fatura do mês de cada cartão e quanto do limite já está comprometido."
    >
      <Estado
        estado={estado}
        aoTentarDeNovo={recarregar}
        textoCarregando="Carregando cartões…"
        textoErro="Não foi possível carregar os cartões."
      >
        {({ cartoes, pessoas }) => {
          if (cartoes.length === 0) {
            return (
              <EstadoVazio
                titulo="Nenhum cartão ainda"
                texto="Cadastre uma conta do tipo dívida em Contas para acompanhar a fatura aqui."
              />
            );
          }
          const cartao = cartoes.find((c) => String(c.conta_id) === escolhido) ?? cartoes[0];
          if (cartao === undefined) return null;
          return (
            <>
              {cartoes.length > 1 && (
                <div className="campo">
                  <label htmlFor="cartao-escolhido">Cartão</label>
                  <select
                    id="cartao-escolhido"
                    value={String(cartao.conta_id)}
                    onChange={(e) => setEscolhido(e.target.value)}
                  >
                    {cartoes.map((c) => (
                      <option key={c.conta_id} value={c.conta_id}>
                        {c.nome}
                      </option>
                    ))}
                  </select>
                </div>
              )}
              <NavegadorMes
                mes={competencia}
                aoMudar={setCompetencia}
                permitirFuturo
                rotulo="Competência da fatura"
              />
              {/* `key`: trocar cartão ou competência recria o bloco, sem mostrar a fatura antiga. */}
              <FaturaDoCartao
                key={`${cartao.conta_id}-${competencia}`}
                cartao={cartao}
                competencia={competencia}
                pessoas={pessoas}
              />
            </>
          );
        }}
      </Estado>
      <Glossario
        termos={[
          "competencia",
          "fatura_aberta_fechada",
          "fatura_propria",
          "fatura_terceiros",
          "credito_estorno",
          "limite_usado",
        ]}
      />
    </Pagina>
  );
}

type FaturaProps = { cartao: ContaSaida; competencia: string; pessoas: PessoaSaida[] };

function FaturaDoCartao({ cartao, competencia, pessoas }: FaturaProps) {
  const linhaId = cartao.linha_credito_id ?? null;
  const buscar = useCallback(
    () =>
      juntar<FaturaSaida, LimiteSaida | null>(
        obterFatura(cartao.conta_id, competencia),
        linhaId === null
          ? Promise.resolve<Leitura<LimiteSaida | null>>({ tipo: "ok", dados: null })
          : obterLimite(linhaId),
      ),
    [cartao.conta_id, competencia, linhaId],
  );
  const { estado, recarregar } = useCarga(buscar);

  return (
    <Estado
      estado={estado}
      aoTentarDeNovo={recarregar}
      textoCarregando="Carregando fatura…"
      textoErro="Não foi possível carregar a fatura."
    >
      {([fatura, limite]) => (
        <>
          <Cartao titulo={`Fatura de ${cartao.nome}`}>
            <SituacaoDaFatura fatura={fatura} />
            <dl className="resumo">
              <div>
                <dt>Total da fatura</dt>
                <dd>{formatarMoeda(fatura.total)}</dd>
              </div>
              <div>
                <dt>
                  <Termo id="fatura_propria">Própria</Termo>
                </dt>
                <dd>{formatarMoeda(fatura.propria)}</dd>
              </div>
              <div>
                <dt>
                  <Termo id="fatura_terceiros">Terceiros</Termo>
                </dt>
                <dd>{formatarMoeda(fatura.terceiros)}</dd>
              </div>
            </dl>
          </Cartao>
          <ItensDaFatura itens={fatura.itens} pessoas={pessoas} />
          <LimiteDaLinha limite={limite} />
        </>
      )}
    </Estado>
  );
}

function SituacaoDaFatura({ fatura }: { fatura: FaturaSaida }) {
  if (fatura.situacao === null || fatura.fechamento === null) {
    return (
      <p className="texto-suave">
        Este cartão ainda não tem dia de fechamento cadastrado, então não dá para saber se a
        fatura está <Termo id="fatura_aberta_fechada">aberta ou fechada</Termo>.
      </p>
    );
  }
  const aberta = fatura.situacao === "aberta";
  return (
    <p className="texto-suave">
      <span className={aberta ? "etiqueta" : "etiqueta etiqueta-neutra"}>
        {aberta ? "Aberta" : "Fechada"}
      </span>{" "}
      {aberta ? "Fecha em " : "Fechou em "}
      {formatarData(fatura.fechamento)}. <Termo id="fatura_aberta_fechada">O que significa?</Termo>
    </p>
  );
}

function NomeDaPessoa({ item, pessoas }: { item: ItemFaturaSaida; pessoas: PessoaSaida[] }) {
  if (item.pessoa_id === null) return <>Própria</>;
  const pessoa = pessoas.find((p) => p.pessoa_id === item.pessoa_id);
  return <>Terceiro: {pessoa?.nome ?? "pessoa não encontrada"}</>;
}

function ItensDaFatura({ itens, pessoas }: { itens: ItemFaturaSaida[]; pessoas: PessoaSaida[] }) {
  if (itens.length === 0) {
    return (
      <EstadoVazio titulo="Fatura sem itens" texto="Nenhuma compra caiu nesta competência." />
    );
  }
  return (
    <ul className="lista" aria-label="Itens da fatura">
      {itens.map((item) => {
        // Valor com sinal de menos = crédito (estorno) que abate a fatura. Só rotula; não soma.
        const credito = item.valor.startsWith("-");
        return (
          <li key={`${item.transacao_id}-${item.parcela}`} className="lista-item lista-item-coluna">
            <div className="conta-resumo">
              <span className="conta-nome">
                {item.descricao ?? "Sem descrição"}
                {credito ? (
                  <span className="etiqueta etiqueta-neutra">crédito de estorno</span>
                ) : (
                  item.parcelas > 1 && (
                    <span className="etiqueta">
                      parcela {item.parcela} de {item.parcelas}
                    </span>
                  )
                )}
              </span>
              <span className="conta-saldo">{formatarMoeda(item.valor)}</span>
            </div>
            <span className="texto-suave">
              Compra de {formatarData(item.data_compra)} · <NomeDaPessoa item={item} pessoas={pessoas} />
            </span>
          </li>
        );
      })}
    </ul>
  );
}

function LimiteDaLinha({ limite }: { limite: LimiteSaida | null }) {
  if (limite === null) {
    return (
      <Cartao titulo="Limite da linha de crédito">
        <p className="texto-suave">Este cartão não está ligado a uma linha de crédito.</p>
      </Cartao>
    );
  }
  return (
    <Cartao titulo="Limite da linha de crédito">
      <dl className="resumo">
        <div>
          <dt>Limite</dt>
          <dd>{formatarMoeda(limite.limite)}</dd>
        </div>
        <div>
          <dt>
            <Termo id="limite_usado">Usado</Termo>
          </dt>
          <dd>{formatarMoeda(limite.usado)}</dd>
        </div>
        <div>
          <dt>Disponível</dt>
          <dd>{formatarMoeda(limite.disponivel)}</dd>
        </div>
      </dl>
      {limite.disponivel.startsWith("-") && (
        <p className="texto-suave">
          O disponível está negativo: as compras passaram do limite. Nada bloqueia a compra, mas
          vale conferir a fatura.
        </p>
      )}
    </Cartao>
  );
}
