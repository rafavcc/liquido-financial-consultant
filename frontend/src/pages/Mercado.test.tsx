import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen, within } from "@testing-library/react";
import { cloneElement, type ReactElement } from "react";
import { api } from "../api/client";
import { fixtureMercadoProjecao } from "../test/fixtures";
import { Mercado } from "./Mercado";

vi.mock("../api/client", async (orig) => {
  const real = await orig<typeof import("../api/client")>();
  return { ...real, api: { market: vi.fn(), refreshMarket: vi.fn() } };
});
// jsdom não mede layout: o container responsivo recebe um tamanho fixo.
vi.mock("recharts", async (orig) => {
  const real = await orig<typeof import("recharts")>();
  return { ...real, ResponsiveContainer: ({ children }: { children: ReactElement }) => cloneElement(children, { width: 600, height: 260 }) };
});
const mocked = vi.mocked(api, true);

function setup() {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  render(
    <QueryClientProvider client={qc}>
      <Mercado />
    </QueryClientProvider>,
  );
}

test("mostra indicadores, tabela de projeção, fonte e data base do Tesouro", async () => {
  mocked.market.mockResolvedValue({ ...fixtureMercadoProjecao, tesouro_data_base: "2026-11-18" });
  setup();
  expect(await screen.findByText("13,75%")).toBeInTheDocument();
  expect(screen.getByText("13,65%")).toBeInTheDocument();
  expect(screen.getByText("4,63%")).toBeInTheDocument();
  expect(screen.getByText(/ref\. 10\/2026/)).toBeInTheDocument();
  const tabela = screen.getByRole("table");
  expect(within(tabela).getByRole("columnheader", { name: "IPCA projetado" })).toBeInTheDocument();
  expect(within(tabela).getByText("2027")).toBeInTheDocument();
  expect(within(tabela).getByText("12,75%")).toBeInTheDocument();
  expect(screen.getByText(/Focus 13\/11\/2026/)).toBeInTheDocument();
  expect(await screen.findByText("Selic no fim do ano", { selector: ".recharts-legend-item-text" })).toBeInTheDocument();
  expect(screen.getByText("IPCA projetado", { selector: ".recharts-legend-item-text" })).toBeInTheDocument();
  expect(screen.getByText(/Ano corrente inclui meses já divulgados/)).toBeInTheDocument();
  expect(screen.getByText(/Tesouro Direto.*18\/11\/2026/)).toBeInTheDocument();
});

test("sem projeção mostra estado vazio", async () => {
  mocked.market.mockResolvedValue({ ...fixtureMercadoProjecao, projecao: [], fonte_projecao: null });
  setup();
  expect(await screen.findByText(/Sem projeções disponíveis/)).toBeInTheDocument();
});
