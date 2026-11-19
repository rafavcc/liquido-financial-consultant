import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { cloneElement } from "react";
import { ProductDetail } from "./ProductDetail";
import { fixtureDetail, fixtureMercadoProjecao, fixtureResponse } from "../test/fixtures";

// jsdom não tem layout: o ResponsiveContainer recebe tamanho fixo para não emitir avisos.
vi.mock("recharts", async (importOriginal) => {
  const mod = await importOriginal<typeof import("recharts")>();
  const Fixed = ({ children }: { children: React.ReactElement }) =>
    cloneElement(children, { width: 400, height: 200 } as object);
  return { ...mod, ResponsiveContainer: Fixed };
});

const mercado = fixtureMercadoProjecao;

test("detalhe mostra IR, omite IOF zerado e traz Premissas", () => {
  render(<ProductDetail result={fixtureDetail} mercado={mercado} open onOpenChange={() => {}} />);
  const dialog = screen.getByRole("dialog", { name: "CDB Banco Alfa" });
  const ir = within(dialog).getByText("IR").closest("tr")!;
  expect(within(ir).getByText("R$ 264,42")).toBeInTheDocument();
  expect(within(dialog).queryByText("IOF")).toBeNull();
  expect(within(dialog).getByRole("heading", { name: "Premissas" })).toBeInTheDocument();
  expect(within(dialog).getByText(/Focus 13\/11\/2026 — Selic 12,75% em 2027/)).toBeInTheDocument();
  expect(within(dialog).getByText("R$ 11.498,38")).toBeInTheDocument();
  expect(within(dialog).getByText("Solicitar resgate até")).toBeInTheDocument();
});

test("produto sem alerta de projeção mostra rentabilidade prefixada", () => {
  const pre = { ...fixtureDetail, alertas: [] };
  render(<ProductDetail result={pre} mercado={mercado} open onOpenChange={() => {}} />);
  expect(screen.getByText(/sem dependência de projeção/)).toBeInTheDocument();
});

test("resultado indisponível mostra alertas e não mostra decomposição", () => {
  const off = {
    ...fixtureDetail, secao: "INDISPONIVEL" as const, resgatavel: false, valor_bruto: null, valor_liquido: null,
    rentab_liquida: null, taxa_liquida_aa: null, serie: [],
    alertas: [{ code: "ABAIXO_MINIMO" as const, message: "Valor abaixo do mínimo de R$ 100.000,00" }],
  };
  render(<ProductDetail result={off} mercado={fixtureResponse.mercado} open onOpenChange={() => {}} />);
  expect(screen.getByText(/abaixo do mínimo de R\$ 100\.000,00/)).toBeInTheDocument();
  expect(screen.getByText(/não há valor calculado/i)).toBeInTheDocument();
  expect(screen.queryByText("Rendimento bruto")).toBeNull();
});

test("Escape fecha o detalhe", async () => {
  const onOpenChange = vi.fn();
  render(<ProductDetail result={fixtureDetail} mercado={mercado} open onOpenChange={onOpenChange} />);
  await userEvent.keyboard("{Escape}");
  expect(onOpenChange).toHaveBeenCalledWith(false);
});

test("Rendimento bruto zerado é omitido", () => {
  const zero = { ...fixtureDetail, valor_bruto: "10000", valor_liquido: "10000" };
  render(<ProductDetail result={zero} mercado={mercado} open onOpenChange={() => {}} />);
  expect(screen.queryByText("Rendimento bruto")).toBeNull();
  expect(screen.getByText("Valor líquido")).toBeInTheDocument();
});

test("chip Isento de IR segue a lista isentos recebida", () => {
  const { rerender } = render(
    <ProductDetail result={fixtureDetail} mercado={mercado} open onOpenChange={() => {}} isentoTypes={["CDB"]} />,
  );
  expect(screen.getByText("Isento de IR")).toBeInTheDocument();
  rerender(<ProductDetail result={fixtureDetail} mercado={mercado} open onOpenChange={() => {}} isentoTypes={["LCI"]} />);
  expect(screen.queryByText("Isento de IR")).toBeNull();
});

test("código de alerta desconhecido não quebra e mostra a mensagem", () => {
  const r = { ...fixtureDetail, alertas: [{ code: "NOVO" as never, message: "Aviso novo do servidor" }] };
  render(<ProductDetail result={r} mercado={mercado} open onOpenChange={() => {}} />);
  expect(screen.getByText("Aviso novo do servidor")).toBeInTheDocument();
});

test("sobra do Tesouro aparece na decomposição quando maior que zero", () => {
  const r = { ...fixtureDetail, sobra: "172.07" };
  render(<ProductDetail result={r} mercado={mercado} open onOpenChange={() => {}} />);
  const row = screen.getByText("Sobra não aplicada (fica parada)").closest("tr")!;
  expect(within(row).getByText("R$ 172,07")).toBeInTheDocument();
});

test("sem sobra, a linha não aparece", () => {
  render(<ProductDetail result={fixtureDetail} mercado={mercado} open onOpenChange={() => {}} />);
  expect(screen.queryByText(/Sobra não aplicada/)).toBeNull();
});

test("rentabilidade negativa no detalhe usa sinal correto e tom de perda", () => {
  const r = { ...fixtureDetail, rentab_liquida: "-0.0193", taxa_liquida_aa: "-0.289" };
  render(<ProductDetail result={r} mercado={mercado} open onOpenChange={() => {}} />);
  expect(screen.getByText("−1,93%")).toHaveClass("text-neg");
  expect(screen.getByText("−28,90%")).toHaveClass("text-neg");
});
