import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { ProductCard } from "./ProductCard";
import { indexLabel } from "../lib/labels";
import { fixtureResult } from "../test/fixtures";


test("ProductCard mostra alerta de projeção e posição", () => {
  render(<ProductCard result={{ ...fixtureResult, valor_liquido: "71840.10" }} rank={1} />);
  expect(screen.getByText("#1")).toBeInTheDocument();
  expect(screen.getByText(/Depende de projeção/)).toBeInTheDocument();
  expect(screen.getByText("R$ 71.840,10")).toBeInTheDocument();
  expect(screen.getByText("112% do CDI")).toBeInTheDocument();
  expect(screen.getByText("+43,68%")).toBeInTheDocument();
  expect(screen.getByText(/11,80% a\.a\. líquido/)).toBeInTheDocument();
});

test("ProductCard dispara onSelect ao clicar", async () => {
  const onSelect = vi.fn();
  render(<ProductCard result={fixtureResult} rank={2} onSelect={onSelect} />);
  await userEvent.click(screen.getByRole("button"));
  expect(onSelect).toHaveBeenCalledWith(fixtureResult);
});

test("ProductCard de LCI mostra isenção de IR e sem posição na seção vermelha", () => {
  const lci = { ...fixtureResult, product: { ...fixtureResult.product, tipo: "LCI" as const }, secao: "VENCE_DEPOIS" as const };
  render(<ProductCard result={lci} />);
  expect(screen.getByText("Isento de IR")).toBeInTheDocument();
  expect(screen.queryByText(/^#/)).toBeNull();
});

test.each([
  ["PCT_CDI", "1.12", "112% do CDI"],
  ["CDI_MAIS", "0.012", "CDI + 1,20%"],
  ["IPCA_MAIS", "0.07", "IPCA + 7,00%"],
  ["PRE", "0.142", "Pré 14,20%"],
  ["SELIC", "0.0005", "Selic + 0,05%"],
] as const)("indexLabel %s", (indexador, taxa, esperado) => {
  expect(indexLabel(indexador, taxa)).toBe(esperado);
});
