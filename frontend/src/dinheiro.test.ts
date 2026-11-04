import { formatarMoeda } from "./dinheiro";

// Todo código de produção do front, exceto o cliente gerado, testes e a configuração dos testes.
const fontes = import.meta.glob(
  ["./**/*.{ts,tsx}", "!./**/*.test.{ts,tsx}", "!./api/gerado/**", "!./setupTests.ts"],
  { query: "?raw", import: "default", eager: true },
) as Record<string, string>;

describe("dinheiro", () => {
  it("formata_texto_decimal", () => {
    expect(formatarMoeda("0.30")).toBe("R$ 0,30");
    expect(formatarMoeda("1234.56")).toBe("R$ 1.234,56");
    expect(formatarMoeda("-1526.59")).toBe("-R$ 1.526,59");
    expect(formatarMoeda("abc")).toBe("abc");
    expect(formatarMoeda("1.5")).toBe("1.5");
  });

  it("sem_float", () => {
    // Acima de 2^53 um `number` perderia dígitos; o texto passa intacto.
    expect(formatarMoeda("12345678901234567.89")).toBe("R$ 12.345.678.901.234.567,89");

    // Nenhuma conversão numérica nem aritmética de valor no código do front (ADR 015).
    expect(Object.keys(fontes).length).toBeGreaterThan(0);
    const proibido = /\b(parseFloat|parseInt|toFixed|Math\.|Number\(|BigInt|Intl\.NumberFormat)/;
    const achados = Object.entries(fontes)
      .filter(([, codigo]) => proibido.test(codigo))
      .map(([arquivo]) => arquivo);
    expect(achados).toEqual([]);
  });
});
