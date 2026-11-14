import { useCallback, useState } from "react";

import type { ContaSaida, GastoRealSaida, ReceitaSaida } from "../api/gerado";
import { type Leitura, listarContas, obterGastoReal, obterReceita } from "../api/leitura";
import { mesAtual } from "../datas";
import { formatarMoeda } from "../dinheiro";
import { Cartao, EstadoVazio, Pagina } from "../ui/componentes";
import { Glossario, Termo } from "./Glossario";
import { Estado, NavegadorMes } from "./pecas";
import { primeiraFalha, useCarga } from "./useCarga";

type Dados = { gasto: GastoRealSaida; receita: ReceitaSaida; contas: ContaSaida[] };

/**
 * Gasto real e receita de caixa de um mês. O total e o gasto de cada conta chegam calculados pelo
 * banco (o que conta e o que não conta como gasto real é regra do servidor, ADR 046); a tela só
 * escolhe o mês e mostra. O mês começa no corrente e dá para voltar a meses anteriores.
 */
export function GastoReal() {
  const [mes, setMes] = useState(mesAtual);
  return (
    <Pagina titulo="Gasto do mês" descricao="O que você gastou e o que entrou no caixa no mês.">
      <NavegadorMes mes={mes} aoMudar={setMes} permitirFuturo={false} rotulo="Mês de referência" />
      {/* `key={mes}`: ao trocar de mês o React descarta este bloco e cria outro do zero, então o
          valor do mês antigo nunca fica na tela sob o título do mês novo. */}
      <DadosDoMes key={mes} mes={mes} />
      <Glossario termos={["gasto_real", "receita_caixa"]} />
    </Pagina>
  );
}

function DadosDoMes({ mes }: { mes: string }) {
  const buscar = useCallback(async (): Promise<Leitura<Dados>> => {
    const [gasto, receita, contas] = await Promise.all([
      obterGastoReal(mes),
      obterReceita(mes),
      listarContas(),
    ]);
    const falha = primeiraFalha([gasto, receita, contas]);
    if (falha !== null) return falha;
    if (gasto.tipo !== "ok" || receita.tipo !== "ok" || contas.tipo !== "ok") {
      return { tipo: "erro" };
    }
    return {
      tipo: "ok",
      dados: { gasto: gasto.dados, receita: receita.dados, contas: contas.dados },
    };
  }, [mes]);
  const { estado, recarregar } = useCarga<Dados>(buscar);

  return (
      <Estado
        estado={estado}
        aoTentarDeNovo={recarregar}
        textoCarregando="Carregando o mês…"
        textoErro="Não foi possível carregar o gasto e a receita do mês."
      >
        {({ gasto, receita, contas }) => (
          <>
            <div className="grade">
              <Cartao>
                <h2>
                  <Termo id="gasto_real">Gasto real</Termo>
                </h2>
                <p className="valor-grande">{formatarMoeda(gasto.total)}</p>
              </Cartao>
              <Cartao>
                <h2>
                  <Termo id="receita_caixa">Receita de caixa</Termo>
                </h2>
                <p className="valor-grande">{formatarMoeda(receita.caixa)}</p>
              </Cartao>
            </div>
            {gasto.por_conta.length === 0 ? (
              <EstadoVazio
                titulo="Nenhum gasto neste mês"
                texto="Quando houver gasto real lançado neste mês, ele aparece aqui por conta."
              />
            ) : (
              <ul className="lista" aria-label="Gasto real por conta">
                {gasto.por_conta.map((linha) => (
                  <li key={linha.conta_id} className="lista-item">
                    <span className="conta-nome">
                      {contas.find((c) => c.conta_id === linha.conta_id)?.nome ??
                        "Conta não encontrada"}
                    </span>
                    <span className="conta-saldo">{formatarMoeda(linha.valor)}</span>
                  </li>
                ))}
              </ul>
            )}
          </>
        )}
      </Estado>
  );
}
