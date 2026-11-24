import { formatBRL, formatDate, formatPct, formatPctSigned, isNegativePct } from "./format";

test("formatBRL", () => {
  expect(formatBRL("71840.1")).toBe("R$ 71.840,10");
  expect(formatBRL(null)).toBe("—");
});
test("formatBRL com precisão longa arredonda na apresentação", () => {
  expect(formatBRL("65179.91649370854229961760551")).toBe("R$ 65.179,92");
});
test("formatPct", () => {
  expect(formatPct("0.1365")).toBe("13,65%");
  expect(formatPct("1.12", 0)).toBe("112%");
  expect(formatPct("0.012", 2)).toBe("1,20%");
});
test("formatDate", () => expect(formatDate("2029-06-15")).toBe("15/06/2029"));

test("percentuais negativos e com sinal", () => {
  expect(formatPct("-0.0193")).toBe("−1,93%");
  expect(formatPct("-0.00001")).toBe("0,00%");
  expect(formatPctSigned("0.1365")).toBe("+13,65%");
  expect(formatPctSigned("-0.0193")).toBe("−1,93%");
  expect(formatPctSigned("0")).toBe("0,00%");
  expect(isNegativePct("-0.0193")).toBe(true);
  expect(isNegativePct("-0.00001")).toBe(false);
  expect(isNegativePct("0.01")).toBe(false);
});

test("idadeLabel: hoje, há 1 dia, há N dias", async () => {
  const { idadeLabel } = await import("./format");
  expect(idadeLabel(0)).toBe("hoje");
  expect(idadeLabel(1)).toBe("há 1 dia");
  expect(idadeLabel(3)).toBe("há 3 dias");
});
