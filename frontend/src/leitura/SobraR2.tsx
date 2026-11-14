import type { ContaSaida, ItemR2Saida, RecorrenteSaida, SituacaoR2Saida } from "../api/gerado";
import { type Leitura, listarContas, listarRecorrentes, obterR2 } from "../api/leitura";
import { formatarData } from "../datas";
import { formatarMoeda } from "../dinheiro";
import { Cartao, EstadoVazio, Pagina } from "../ui/componentes";
import { Glossario, Termo } from "./Glossario";
import { Estado } from "./pecas";
import { primeiraFalha, useCarga } from "./useCarga";

type Dados = { r2: SituacaoR2Saida; contas: ContaSaida[]; recorrentes: RecorrenteSaida[] };

async function buscarR2(): Promise<Leitura<Dados>> {
  const [r2, contas, recorrentes] = await Promise.all([
    obterR2(),
    listarContas(),
    listarRecorrentes(),
  ]);
  const falha = primeiraFalha([r2, contas, recorrentes]);
  if (falha !== null) return falha;
  if (r2.tipo !== "ok" || contas.tipo !== "ok" || recorrentes.tipo !== "ok") {
    return { tipo: "erro" };
  }
  return {
    tipo: "ok",
    dados: { r2: r2.dados, contas: contas.dados, recorrentes: recorrentes.dados },
  };
}

/** Aviso de sobra não confiável: aparece sempre que a API conta pendências de vencimento. */
export function AvisoSobraNaoConfiavel() {
  return (
    <div className="resultado resultado-atencao" role="note">
      <p>
        <strong>
          <Termo id="sobra_nao_confiavel">Sobra não confiável</Termo>
        </strong>
        : há cartão com dívida sem vencimento ou fechamento cadastrado. Cadastre o vencimento para
        o número valer.
      </p>
    </div>
  );
}

const GRUPOS: { grupo: string; titulo: string }[] = [
  { grupo: "receita", titulo: "Receitas esperadas" },
  { grupo: "fixo", titulo: "Contas fixas" },
  { grupo: "fatura", titulo: "Faturas próprias" },
  { grupo: "vencida", titulo: "Vencidas (ficam fora da sobra)" },
];

/**
 * Sobra do R2: quanto sobra depois dos compromissos dos próximos dias. Disponível, compromissos,
 * sobra, alerta e cada item vêm calculados pelo banco (ADR 048); a tela só exibe, e cruza os ids
 * com os nomes de contas e recorrentes (a API não manda o nome nos itens).
 */
export function SobraR2() {
  const { estado, recarregar } = useCarga(buscarR2);
  return (
    <Pagina
      titulo="Sobra (R2)"
      descricao="Quanto sobra depois do que vence nos próximos dias."
    >
      <Estado
        estado={estado}
        aoTentarDeNovo={recarregar}
        textoCarregando="Carregando a sobra…"
        textoErro="Não foi possível carregar a sobra."
      >
        {({ r2, contas, recorrentes }) => (
          <>
            {r2.pendencias_vencimento > 0 && <AvisoSobraNaoConfiavel />}
            <Cartao>
              <h2>
                <Termo id="sobra">Sobra</Termo> até {formatarData(r2.data_fim)}
              </h2>
              <p className="valor-grande">{formatarMoeda(r2.sobra)}</p>
              {r2.alerta && (
                <p className="erro-form" role="note">
                  A sobra está negativa: falta dinheiro para o que vence no horizonte.
                </p>
              )}
              <dl className="resumo">
                <div>
                  <dt>
                    <Termo id="horizonte">Horizonte</Termo>
                  </dt>
                  <dd>{r2.horizonte_dias} dias</dd>
                </div>
                <div>
                  <dt>
                    <Termo id="disponivel">Disponível</Termo>
                  </dt>
                  <dd>{formatarMoeda(r2.disponivel)}</dd>
                </div>
                <div>
                  <dt>
                    <Termo id="compromissos">Compromissos</Termo>
                  </dt>
                  <dd>{formatarMoeda(r2.compromissos)}</dd>
                </div>
              </dl>
            </Cartao>
            {r2.itens.length === 0 ? (
              <EstadoVazio
                titulo="Nada previsto no horizonte"
                texto="Não há receita, conta fixa nem fatura própria nos próximos dias."
              />
            ) : (
              GRUPOS.map(({ grupo, titulo }) => {
                const itens = r2.itens.filter((i) => i.grupo === grupo);
                if (itens.length === 0) return null;
                return (
                  <section key={grupo} aria-label={titulo}>
                    <h2 className="subtitulo">
                      {grupo === "vencida" ? <Termo id="vencidas">{titulo}</Termo> : titulo}
                    </h2>
                    <ul className="lista">
                      {itens.map((item, indice) => (
                        <li
                          key={`${grupo}-${indice}`}
                          className="lista-item lista-item-coluna"
                        >
                          <ItemDoR2 item={item} contas={contas} recorrentes={recorrentes} />
                        </li>
                      ))}
                    </ul>
                  </section>
                );
              })
            )}
          </>
        )}
      </Estado>
      <Glossario
        termos={[
          "sobra",
          "horizonte",
          "disponivel",
          "compromissos",
          "parcial",
          "vencidas",
          "sobra_nao_confiavel",
        ]}
      />
    </Pagina>
  );
}

type ItemProps = { item: ItemR2Saida; contas: ContaSaida[]; recorrentes: RecorrenteSaida[] };

function ItemDoR2({ item, contas, recorrentes }: ItemProps) {
  const conta = contas.find((c) => c.conta_id === item.conta_id)?.nome ?? "conta não encontrada";
  const nome =
    item.grupo === "fatura"
      ? `Fatura de ${conta}${item.competencia === null ? "" : ` (${item.competencia})`}`
      : (recorrentes.find((r) => r.recorrente_id === item.recorrente_id)?.nome ??
        "Recorrente não encontrado");
  return (
    <>
      <div className="conta-resumo">
        <span className="conta-nome">
          {nome}
          {item.parcial === true && (
            <span className="etiqueta etiqueta-neutra">
              <Termo id="parcial">fatura aberta (parcial)</Termo>
            </span>
          )}
        </span>
        <span className="conta-saldo">{formatarMoeda(item.valor)}</span>
      </div>
      <span className="texto-suave">
        Data: {formatarData(item.data)}
        {item.grupo === "fatura" && item.bruto !== null && ` · fatura de ${formatarMoeda(item.bruto)}`}
        {item.grupo === "fatura" && item.pago !== null && ` · já paga ${formatarMoeda(item.pago)}`}
        {item.grupo !== "fatura" && ` · ${conta}`}
      </span>
    </>
  );
}
