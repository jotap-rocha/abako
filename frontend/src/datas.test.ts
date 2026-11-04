import { formatarData, hojeEmSaoPaulo } from "./datas";

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
});
