// Datas de negócio são datas civis de America/Sao_Paulo, no formato "AAAA-MM-DD" (ADR 012).
// Aqui só se lê o relógio para sugerir "hoje" num campo e se muda a apresentação. Quem decide se
// a data vale (por exemplo, recusar data futura) é o servidor.

const FUSO = "America/Sao_Paulo";
const DATA_ISO = /^(\d{4})-(\d{2})-(\d{2})$/;

/** Hoje em São Paulo, "AAAA-MM-DD", não importa o fuso configurado no computador. */
export function hojeEmSaoPaulo(agora: Date = new Date()): string {
  // Monta AAAA-MM-DD pelas partes, sem depender de como um idioma escreve a data inteira.
  const partes = new Intl.DateTimeFormat("en-US", {
    timeZone: FUSO,
    year: "numeric",
    month: "2-digit",
    day: "2-digit",
  }).formatToParts(agora);
  const parte = (tipo: Intl.DateTimeFormatPartTypes) =>
    partes.find((p) => p.type === tipo)?.value ?? "";
  return `${parte("year")}-${parte("month")}-${parte("day")}`;
}

/** "2026-11-04" → "04/11/2026". Texto fora do formato volta como veio. */
export function formatarData(data: string): string {
  const partes = DATA_ISO.exec(data);
  if (partes === null) return data;
  const [, ano, mes, dia] = partes;
  return `${dia}/${mes}/${ano}`;
}
