import { useCallback, useState } from "react";

import type {
  BeneficiosSaida,
  ContaSaida,
  DecisaoHistoricoSaida,
  SituacaoValeSaida,
} from "../api/gerado";
import { type Leitura, listarContas } from "../api/leitura";
import { listarDecisoes, obterBeneficios, obterSituacaoVale } from "../api/vale";
import { mesAtual } from "../datas";
import { Glossario } from "../leitura/Glossario";
import { Estado, NavegadorMes } from "../leitura/pecas";
import { primeiraFalha, useCarga } from "../leitura/useCarga";
import { Cartao, Pagina } from "../ui/componentes";
import { Beneficios } from "./Beneficios";
import { Bolsos, Receitas, Resumo, Sobra } from "./Bolsos";
import { Decisao } from "./Decisao";
import { ParametroVale } from "./ParametroVale";

type DadosVale = {
  situacao: SituacaoValeSaida;
  beneficios: BeneficiosSaida;
  decisoes: DecisaoHistoricoSaida[];
  contas: ContaSaida[];
};

/** Busca tudo da página de uma vez; se uma leitura falhar, a falha que vale é devolvida. */
async function buscarTudo(mes: string): Promise<Leitura<DadosVale>> {
  const [situacao, beneficios, decisoes, contas] = await Promise.all([
    obterSituacaoVale(mes),
    obterBeneficios(mes),
    listarDecisoes(mes),
    listarContas(),
  ]);
  const falha = primeiraFalha([situacao, beneficios, decisoes, contas]);
  if (falha !== null) return falha;
  if (
    situacao.tipo !== "ok" ||
    beneficios.tipo !== "ok" ||
    decisoes.tipo !== "ok" ||
    contas.tipo !== "ok"
  ) {
    return { tipo: "erro" };
  }
  return {
    tipo: "ok",
    dados: {
      situacao: situacao.dados,
      beneficios: beneficios.dados,
      decisoes: decisoes.dados,
      contas: contas.dados,
    },
  };
}

/**
 * Vale (VR): a única tela que mostra o vale (ADR 023, 052). Tudo vem pronto da API (crédito,
 * alocação, consumo, resta, sobra, saldo); a tela só exibe. O estado do mês (`sem_conta`,
 * `sem_credito`, `ok`) e se o mês já está encerrado (`mes_encerrado`) também vêm da API: o front
 * não compara datas nem valores.
 */
export function Vale() {
  const [mes, setMes] = useState(mesAtual);
  const buscar = useCallback(() => buscarTudo(mes), [mes]);
  const { estado, recarregar, atualizar } = useCarga(buscar);
  return (
    <Pagina
      titulo="Vale"
      descricao="Vale-refeição (VR) por bolso: o que entrou, o que foi gasto, o que resta e a sobra do mês."
    >
      <NavegadorMes mes={mes} aoMudar={setMes} permitirFuturo={false} rotulo="Mês do vale" />
      <Estado
        estado={estado}
        aoTentarDeNovo={recarregar}
        textoCarregando="Carregando o vale…"
        textoErro="Não foi possível carregar o vale."
      >
        {(d) => <Conteudo dados={d} mes={mes} aoGravar={atualizar} />}
      </Estado>
      <Glossario termos={["vale", "bolso", "resta", "sobra_vale", "estouro"]} />
    </Pagina>
  );
}

function Conteudo({
  dados,
  mes,
  aoGravar,
}: {
  dados: DadosVale;
  mes: string;
  aoGravar: () => void;
}) {
  const { situacao, beneficios, decisoes, contas } = dados;
  const contasDeBeneficio = contas.filter((c) => c.tipo === "beneficio");
  return (
    <>
      {situacao.estado === "sem_conta" ? (
        <Cartao titulo="Nenhuma conta marcada como VR">
          <p>
            O abako ainda não sabe qual das suas contas de benefício é o vale-refeição neste mês.
            Marque a conta abaixo para ver o crédito, os bolsos e a sobra.
          </p>
          <ParametroVale contas={contasDeBeneficio} mes={mes} inicial={null} aoGravar={aoGravar} />
        </Cartao>
      ) : (
        <>
          {situacao.estado === "sem_credito" && (
            <div className="resultado resultado-atencao" role="status">
              <p>
                Este mês não teve crédito no VR. Sem crédito não há orçamento a estourar, então não
                há alerta; o que foi gasto e o ajuste do mês anterior aparecem abaixo.
              </p>
            </div>
          )}
          <Resumo situacao={situacao} />
          <Bolsos situacao={situacao} />
          <Sobra situacao={situacao} />
          <Decisao
            situacao={situacao}
            historico={decisoes}
            aoGravar={aoGravar}
          />
          <Receitas situacao={situacao} />
          <Cartao titulo="Marcação do VR">
            <ParametroVale
              contas={contasDeBeneficio}
              mes={mes}
              inicial={{
                contaId: situacao.conta_vr_id,
                base: situacao.base_trabalho,
                destino: situacao.destino_padrao,
              }}
              aoGravar={aoGravar}
            />
          </Cartao>
        </>
      )}
      <Beneficios beneficios={beneficios} contas={contas} />
    </>
  );
}
