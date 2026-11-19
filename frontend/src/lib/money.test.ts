import { subtractMoney } from "./money";

test("subtractMoney é exato e arredonda cada parcela a centavos (half-even)", () => {
  expect(subtractMoney("70439.1023", "50000")).toBe("20439.10");
  expect(subtractMoney("0.30", "0.10")).toBe("0.20");
  expect(subtractMoney("10.005", "0")).toBe("10.00");
  expect(subtractMoney("10.015", "0")).toBe("10.02");
  expect(subtractMoney("100", "100.00")).toBe("0.00");
  expect(subtractMoney("100", "150.5")).toBe("-50.50");
});
