import { formatarDecimal, formatarMoeda, lerValorDigitado } from "./dinheiro";

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

  it("formata_decimal_sem_conta", () => {
    expect(formatarDecimal("9.99")).toBe("9,99");
    expect(formatarDecimal("12345678901234567.89")).toBe("12345678901234567,89");
    expect(formatarDecimal("3")).toBe("3");
    expect(formatarDecimal("abc")).toBe("abc");
  });

  it("le_valor_digitado_no_jeito_brasileiro", () => {
    const casos: [string, string | null][] = [
      ["1.234,56", "1234.56"],
      ["1234,56", "1234.56"],
      ["R$ 1.234,56", "1234.56"],
      ["-50,5", "-50.5"],
      ["-R$ 50,00", "-50.00"],
      ["1000", "1000"],
      ["12.5", "12.5"],
      ["1.234", "1234"],
      ["1.234.567", "1234567"],
      ["0,30", "0.30"],
      ["123456789012,34", "123456789012.34"],
      ["1234567890123", null], // 13 dígitos: a API aceita até 12
      ["1,234", null], // 3 casas decimais
      ["1.23,45", null], // milhar mal agrupado
      ["dez", null],
      ["", null],
      ["-", null],
      ["1e3", null],
    ];
    for (const [digitado, esperado] of casos) {
      expect([digitado, lerValorDigitado(digitado)]).toEqual([digitado, esperado]);
    }
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
