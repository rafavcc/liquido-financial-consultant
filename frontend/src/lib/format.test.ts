import { formatBRL, formatDate, formatPct } from "./format";

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
