import { decimalToBRLInput, fractionToPercent, percentToFraction } from "./percent";

describe("percentToFraction", () => {
  test.each([
    ["112", "1.12"],
    ["14,2", "0.142"],
    ["13,75", "0.1375"],
    ["0,30", "0.003"],
    ["0,3", "0.003"],
    ["100", "1"],
    ["0", "0"],
    ["0,05", "0.0005"],
    ["7", "0.07"],
    ["007,5", "0.075"],
    ["14.2", "0.142"],
    [" 14,2 ", "0.142"],
    ["200", "2"],
    ["0,1", "0.001"],
  ])("%s -> %s", (input, out) => {
    expect(percentToFraction(input)).toBe(out);
  });

  test.each(["", "abc", "1,2,3", "-5", "14,", ",", "1e3", "1.234,5"])("rejeita %j", (input) => {
    expect(percentToFraction(input)).toBeNull();
  });

  test("não perde precisão onde float perderia", () => {
    expect(percentToFraction("0,29")).toBe("0.0029");
    expect(percentToFraction("1,15")).toBe("0.0115");
    expect(percentToFraction("12,345678")).toBe("0.12345678");
  });
});

describe("fractionToPercent", () => {
  test.each([
    ["0.142", "14,2"],
    ["1.12", "112"],
    ["0.003", "0,3"],
    ["0.1375", "13,75"],
    ["0.14200000", "14,2"],
    ["1", "100"],
    ["0", "0"],
    ["0.0", "0"],
    ["1.1200", "112"],
    ["0.0005", "0,05"],
    ["2", "200"],
  ])("%s -> %s", (input, out) => {
    expect(fractionToPercent(input)).toBe(out);
  });

  test("ida e volta", () => {
    for (const p of ["112", "14,2", "0,3", "13,75", "0,05"]) {
      expect(fractionToPercent(percentToFraction(p) as string)).toBe(p);
    }
  });

  test("vazio ou inválido devolve vazio", () => {
    expect(fractionToPercent(null)).toBe("");
    expect(fractionToPercent("")).toBe("");
    expect(fractionToPercent("x")).toBe("");
  });
});

describe("decimalToBRLInput", () => {
  test.each([
    ["1000", "1.000"],
    ["1000.00", "1.000"],
    ["1000.50", "1.000,50"],
    ["1000.55", "1.000,55"],
    ["0", "0"],
    ["0.00", "0"],
    ["100000.000", "100.000"],
  ])("%s -> %s", (input, out) => {
    expect(decimalToBRLInput(input)).toBe(out);
  });
  test("vazio", () => {
    expect(decimalToBRLInput(null)).toBe("");
  });
});
