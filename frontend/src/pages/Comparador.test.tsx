import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { Comparador } from "./Comparador";
import { api } from "../api/client";
import { fixtureResponse } from "../test/fixtures";

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
