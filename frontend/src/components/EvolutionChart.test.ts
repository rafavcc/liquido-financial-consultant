import { niceScale } from "./EvolutionChart";

test("niceScale usa passo redondo e domínio alinhado", () => {
  const { domain, ticks } = niceScale(50000, 72100);
  expect(domain).toEqual([50000, 75000]);
  expect(ticks).toEqual([50000, 55000, 60000, 65000, 70000, 75000]);
});
