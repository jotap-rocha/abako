// Só tradução de códigos da API para texto de tela. Nenhuma regra: o código já vem decidido.

/** Rota da tela de parâmetros (task 19). Até ela existir, o link cai em "página não encontrada". */
export const ROTA_PARAMETROS = "/parametros";

const NIVEIS: Record<string, string> = {
  critica: "Crítica",
  atencao: "Atenção",
  saudavel: "Saudável",
};

/** Nível da reserva em palavras; nulo = ainda sem meta configurada. */
export function rotuloDoNivel(nivel: string | null): string {
  if (nivel === null) return "Sem nível (falta configurar)";
  return NIVEIS[nivel] ?? nivel;
}

const SEVERIDADES: Record<string, string> = { alta: "Alta", media: "Média", baixa: "Baixa" };

export function rotuloDaSeveridade(severidade: string): string {
  return SEVERIDADES[severidade] ?? severidade;
}

/** Ação sugerida por `detalhe` (identificador estável do caso, ADR 049). */
const ACOES: Record<string, string> = {
  reserva_critica: "Reforce a reserva: ela está abaixo da metade da meta.",
  reserva_atencao: "A reserva ainda não chegou à meta; acompanhe o aporte mensal.",
  reserva_gasto_essencial: "Informe o gasto essencial mensal para calcular a meta da reserva.",
  sobra_negativa: "Falta dinheiro para o que vence no horizonte; revise os compromissos.",
  sobra_nao_confiavel: "Cadastre o vencimento e o fechamento do cartão para a sobra ficar confiável.",
  vencidas: "Vincule cada ocorrência vencida ao lançamento que a pagou.",
  vale_trabalho_estourado:
    "O bolso de trabalho do vale gastou mais do que tinha neste mês; veja a página do vale.",
  vale_pessoal_estourado:
    "O bolso pessoal do vale gastou mais do que tinha neste mês; veja a página do vale.",
  divergencia_saldo: "Confira o saldo informado (snapshot) e os lançamentos da conta.",
};

export function acaoSugerida(detalhe: string): string | null {
  return ACOES[detalhe] ?? null;
}

const BOLSOS: Record<string, string> = { trabalho: "trabalho", pessoal: "pessoal" };

/** Nome do bolso em palavras (código desconhecido volta como veio). */
export function rotuloDoBolso(bolso: string): string {
  return BOLSOS[bolso] ?? bolso;
}

const DESTINOS: Record<string, string> = {
  trabalho: "bolso de trabalho",
  pessoal: "bolso pessoal",
  nenhum: "nenhum (a sobra não passa para o mês seguinte)",
};

/** Destino da sobra em palavras. */
export function rotuloDoDestino(destino: string): string {
  return DESTINOS[destino] ?? destino;
}
