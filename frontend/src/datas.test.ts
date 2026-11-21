import { deslocarMes, formatarData, hojeEmSaoPaulo, mesAtual, nomeDoMes, primeiroDiaDoMesAtual } from "./datas";

describe("datas", () => {
  it("hoje_e_o_dia_civil_de_sao_paulo", () => {
    // 02:30 UTC de 5/11 ainda é 23:30 de 4/11 em São Paulo (UTC−3).
    expect(hojeEmSaoPaulo(new Date("2026-11-05T02:30:00Z"))).toBe("2026-11-04");
    expect(hojeEmSaoPaulo(new Date("2026-11-05T03:00:00Z"))).toBe("2026-11-05");
    // Virada de ano e dias com um dígito saem com zero à esquerda.
    expect(hojeEmSaoPaulo(new Date("2027-01-01T02:59:59Z"))).toBe("2026-12-31");
    expect(hojeEmSaoPaulo(new Date("2027-02-03T12:00:00Z"))).toBe("2027-02-03");
  });

  it("formata_data_iso", () => {
    expect(formatarData("2026-11-04")).toBe("04/11/2026");
    expect(formatarData("04/11/2026")).toBe("04/11/2026");
  });

  it("navega_entre_meses_do_calendario", () => {
    expect(deslocarMes("2026-01", -1)).toBe("2025-12");
    expect(deslocarMes("2026-11", 1)).toBe("2026-12");
    expect(deslocarMes("2026-12", 1)).toBe("2027-01");
    expect(deslocarMes("2026-03", -13)).toBe("2025-02");
    expect(mesAtual(new Date("2026-12-01T02:00:00Z"))).toBe("2026-11");
    expect(nomeDoMes("2026-11")).toBe("novembro de 2026");
  });

  it("primeiro_dia_do_mes_atual_usa_o_fuso_de_sao_paulo", () => {
    // 02:00 UTC de 1/12 ainda é novembro em São Paulo; 04:00 UTC já é dezembro.
    expect(primeiroDiaDoMesAtual(new Date("2026-12-01T02:00:00Z"))).toBe("2026-11-01");
    expect(primeiroDiaDoMesAtual(new Date("2026-12-01T04:00:00Z"))).toBe("2026-12-01");
  });
});
