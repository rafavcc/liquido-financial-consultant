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

test("rentabilidade negativa mostra sinal de menos e tom de perda, sem '+'", () => {
  render(<ProductCard result={{ ...fixtureResult, rentab_liquida: "-0.0193", taxa_liquida_aa: "-0.289" }} rank={1} />);
  const chip = screen.getByText("−1,93%");
  expect(chip).toHaveClass("text-neg");
  expect(screen.queryByText(/\+/)).toBeNull();
  expect(screen.getByText(/−28,90% a\.a\. líquido/)).toBeInTheDocument();
});

test("produto vencido mostra a mensagem com a data na seção de indisponíveis", () => {
  const vencido = {
    ...fixtureResult, secao: "INDISPONIVEL" as const, resgatavel: false, valor_liquido: null, valor_bruto: null,
    rentab_liquida: null, taxa_liquida_aa: null,
    alertas: [{ code: "VENCIDO" as const, message: "Produto vencido em 10/11/2026 — atualize ou exclua" }],
  };
  render(<ProductCard result={vencido} />);
  expect(screen.getByText(/Produto vencido em 10\/11\/2026 — atualize ou exclua/)).toBeInTheDocument();
});

test("destaque taxa mostra taxa grande, valor e data de saída", () => {
  render(<ProductCard result={{ ...fixtureResult, valor_liquido: "71840.10" }} destaque="taxa" />);
  expect(screen.getByText("11,80% a.a.")).toBeInTheDocument();
  expect(screen.getByText("R$ 71.840,10 em 16/11/2028")).toBeInTheDocument();
});

test("dominado mostra o selo e o prazo de saída aparece", () => {
  render(<ProductCard result={fixtureResult} dominado hoje="2026-11-24" />);
  expect(screen.getByText("Há opção melhor e mais curta")).toBeInTheDocument();
  expect(screen.getByText("Preso até 15/11/2028")).toBeInTheDocument();
});
