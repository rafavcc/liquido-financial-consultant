import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { Comparador } from "./Comparador";
import { api } from "../api/client";
import { fixtureResponse, fixtureResult } from "../test/fixtures";

const mk = (id: string, nome: string, taxa: string, tipo: "CDB" | "LCI" = "CDB") => ({
  ...fixtureResult,
  product: { ...fixtureResult.product, id, nome, tipo },
  taxa_liquida_aa: taxa,
  valor_liquido: String(50000 * (1 + Number(taxa))),
});
const baixa = mk("baixa", "CDB Baixa", "0.10");
const alta = mk("alta", "CDB Alta", "0.14");
const cdb = mk("cdb-dom", "CDB Dominante", "0.13");
const lci = mk("lci-dom", "LCI Dominada", "0.11", "LCI");

vi.mock("../api/client", async (orig) => {
  const real = await orig<typeof import("../api/client")>();
  return {
    ...real,
    api: {
      simulate: vi.fn(),
      market: vi.fn(),
      refreshMarket: vi.fn(),
      settings: { get: vi.fn() },
    },
  };
});

const mocked = vi.mocked(api, true);

function setup() {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  render(
    <QueryClientProvider client={qc}>
      <Comparador />
    </QueryClientProvider>,
  );
}

beforeEach(() => {
  localStorage.clear();
  mocked.simulate.mockResolvedValue(fixtureResponse);
  mocked.market.mockResolvedValue(fixtureResponse.mercado);
  mocked.refreshMarket.mockRejectedValue(new Error("boom"));
  mocked.settings.get.mockRejectedValue(new Error("offline"));
});

test("falha ao atualizar o mercado mostra mensagem", async () => {
  setup();
  await screen.findByText("CDB Banco Alfa");
  await userEvent.click(screen.getByLabelText("Atualizar dados de mercado"));
  expect(await screen.findByText("Não foi possível atualizar os dados de mercado.")).toBeInTheDocument();
});

test("apagar o valor esconde os cards e mostra a validação", async () => {
  setup();
  await screen.findByText("CDB Banco Alfa");
  await userEvent.clear(screen.getByLabelText("Quanto você quer investir?"));
  await waitFor(() => expect(screen.queryByText("CDB Banco Alfa")).toBeNull(), { timeout: 2000 });
  expect(screen.getByText("Informe um valor maior que zero.")).toBeInTheDocument();
});

test("clicar no card abre o detalhe e Escape fecha", async () => {
  setup();
  await userEvent.click(await screen.findByRole("button", { name: "CDB Banco Alfa" }));
  expect(await screen.findByRole("dialog", { name: "CDB Banco Alfa" })).toBeInTheDocument();
  await userEvent.keyboard("{Escape}");
  await waitFor(() => expect(screen.queryByRole("dialog")).toBeNull());
});

test("sem data: esconde a data, chama a API com SEM_DATA e ordena por taxa", async () => {
  mocked.simulate.mockResolvedValue({ ...fixtureResponse, horizonte: "SEM_DATA", data_alvo: null, vence_ate_data: [baixa, alta] });
  setup();
  await userEvent.click(await screen.findByRole("radio", { name: "Sem data" }));
  expect(screen.queryByLabelText("Preciso do dinheiro em")).toBeNull();
  await waitFor(() => expect(mocked.simulate).toHaveBeenLastCalledWith(expect.any(String), "SEM_DATA", null, expect.anything()));
  expect((screen.getByLabelText("Ordenar por") as HTMLSelectElement).value).toBe("TAXA");
  const titulos = (await screen.findAllByRole("article")).map((a) => a.querySelector("h3")?.textContent);
  expect(titulos).toEqual([alta.product.nome, baixa.product.nome]);
});

test("1 ano mostra a data resolvida pelo backend", async () => {
  mocked.simulate.mockResolvedValue({ ...fixtureResponse, horizonte: "UM_ANO", data_alvo: "2027-11-19" });
  setup();
  await userEvent.click(await screen.findByRole("radio", { name: "1 ano" }));
  expect(await screen.findByText(/Resgate em 19\/11\/2027/)).toBeInTheDocument();
});

test("selo de dominado respeita o filtro", async () => {
  mocked.simulate.mockResolvedValue({ ...fixtureResponse, vence_ate_data: [cdb, lci] });
  setup();
  expect(await screen.findByText("Há opção melhor e mais curta")).toBeInTheDocument();
  await userEvent.click(screen.getByRole("button", { name: "Só isentos" }));
  expect(screen.queryByText("Há opção melhor e mais curta")).toBeNull();
});

test("localStorage inválido cai no padrão", async () => {
  localStorage.setItem("liquido.horizonte", "XYZ");
  localStorage.setItem("liquido.ordenacao", "ABC");
  setup();
  expect(await screen.findByRole("radio", { name: "Escolher data" })).toHaveAttribute("aria-checked", "true");
  expect((screen.getByLabelText("Ordenar por") as HTMLSelectElement).value).toBe("VALOR_LIQUIDO");
});

test("sem data: não resgatável em vence_depois continua visível", async () => {
  const preso = { ...mk("preso", "CDB Preso", "0.12"), secao: "VENCE_DEPOIS" as const, resgatavel: false };
  mocked.simulate.mockResolvedValue({ ...fixtureResponse, horizonte: "SEM_DATA", data_alvo: null, vence_ate_data: [alta], vence_depois: [preso] });
  setup();
  await userEvent.click(await screen.findByRole("radio", { name: "Sem data" }));
  expect(await screen.findByText("CDB Preso")).toBeInTheDocument();
});
