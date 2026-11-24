import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { api } from "../api/client";
import type { ProductView } from "../api/types";
import { fixtureResponse, fixtureResult } from "../test/fixtures";
import { Produtos } from "./Produtos";

vi.mock("../api/client", async (orig) => {
  const real = await orig<typeof import("../api/client")>();
  return {
    ...real,
    api: {
      market: vi.fn(),
      products: { list: vi.fn(), tesouro: vi.fn(), create: vi.fn(), update: vi.fn(), remove: vi.fn(), duplicate: vi.fn() },
    },
  };
});
const mocked = vi.mocked(api, true);

const cdb: ProductView = { ...fixtureResult.product, id: "p1", idade_dias: 3, expirada: false };
const exemplo: ProductView = { ...cdb, id: "p2", idade_dias: null, nome: "LCI Exemplo", tipo: "LCI", exemplo: true, ativo: false };
const tesouro: ProductView = {
  ...cdb, id: "t1", nome: "Tesouro Selic 2029", tipo: "TESOURO_SELIC", indexador: "SELIC", taxa: "0.0003", plataforma: "Tesouro Direto",
  data_vencimento: "2029-03-01", cobertura: "TESOURO",
};

function setup() {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  const invalidate = vi.spyOn(qc, "invalidateQueries");
  render(
    <QueryClientProvider client={qc}>
      <Produtos />
    </QueryClientProvider>,
  );
  return { invalidate };
}

beforeEach(() => {
  mocked.products.list.mockResolvedValue([cdb, exemplo]);
  mocked.products.tesouro.mockResolvedValue([tesouro]);
  mocked.market.mockResolvedValue({ ...fixtureResponse.mercado, tesouro_data_base: "2026-11-18" });
  mocked.products.update.mockResolvedValue(cdb);
  mocked.products.remove.mockResolvedValue(undefined);
  mocked.products.duplicate.mockResolvedValue(cdb);
});

test("lista produtos manuais com chip Exemplo e o Tesouro com data base", async () => {
  setup();
  expect(await screen.findByText("CDB Banco Alfa")).toBeInTheDocument();
  const sec = screen.getByRole("region", { name: "Meus produtos" });
  expect(within(sec).getByText("Exemplo")).toBeInTheDocument();
  const t = screen.getByRole("region", { name: "Tesouro Direto (automático)" });
  expect(within(t).queryByText("Tesouro Selic 2029")).toBeNull(); // recolhido por padrão (são dezenas de títulos)
  await userEvent.click(within(t).getByRole("button", { name: "Mostrar Tesouro Direto" }));
  expect(await within(t).findByText("Tesouro Selic 2029")).toBeInTheDocument();
  expect(await within(t).findByText(/dados de 18\/11\/2026/)).toBeInTheDocument();
  expect(within(t).queryByRole("button", { name: /Editar/ })).toBeNull();
});

test("estado vazio oferece cadastrar o primeiro produto", async () => {
  mocked.products.list.mockResolvedValue([]);
  const user = userEvent.setup();
  setup();
  await user.click(await screen.findByRole("button", { name: "Cadastrar primeiro produto" }));
  expect(screen.getByRole("dialog", { name: "Novo produto" })).toBeInTheDocument();
});

test("switch ativo faz PUT imediato com o produto inteiro e invalida simulação", async () => {
  const user = userEvent.setup();
  const { invalidate } = setup();
  await user.click(await screen.findByRole("switch", { name: "Desativar CDB Banco Alfa" }));
  await waitFor(() => expect(mocked.products.update).toHaveBeenCalledWith("p1", expect.objectContaining({ id: "p1", ativo: false, taxa: "1.12" })));
  await waitFor(() => {
    const keys = invalidate.mock.calls.map((c) => (c[0] as { queryKey: unknown[] }).queryKey[0]);
    expect(keys).toEqual(expect.arrayContaining(["products", "simulate"]));
  });
});

test("duplicar chama a API", async () => {
  const user = userEvent.setup();
  setup();
  await user.click(await screen.findByRole("button", { name: "Duplicar CDB Banco Alfa" }));
  await waitFor(() => expect(mocked.products.duplicate).toHaveBeenCalledWith("p1"));
});

test("excluir pede confirmação e só então remove", async () => {
  const user = userEvent.setup();
  setup();
  await user.click(await screen.findByRole("button", { name: "Excluir CDB Banco Alfa" }));
  const dialog = screen.getByRole("dialog", { name: "Excluir produto?" });
  expect(mocked.products.remove).not.toHaveBeenCalled();
  await user.click(within(dialog).getByRole("button", { name: "Cancelar" }));
  expect(mocked.products.remove).not.toHaveBeenCalled();
  await user.click(screen.getByRole("button", { name: "Excluir CDB Banco Alfa" }));
  await user.click(within(screen.getByRole("dialog")).getByRole("button", { name: "Excluir" }));
  await waitFor(() => expect(mocked.products.remove).toHaveBeenCalledWith("p1"));
});

test("editar abre o formulário preenchido", async () => {
  const user = userEvent.setup();
  setup();
  await user.click(await screen.findByRole("button", { name: "Editar CDB Banco Alfa" }));
  const dialog = screen.getByRole("dialog", { name: "Editar produto" });
  expect(within(dialog).getByLabelText("Nome")).toHaveValue("CDB Banco Alfa");
  expect(within(dialog).getByLabelText("Taxa")).toHaveValue("112");
});

const velha: ProductView = { ...cdb, id: "p3", nome: "CDB Velho", idade_dias: 40, expirada: true };

test("mostra a idade da oferta: hoje, há 1 dia, há N dias", async () => {
  mocked.products.list.mockResolvedValue([
    { ...cdb, idade_dias: 0, nome: "A" }, { ...cdb, id: "q2", idade_dias: 1, nome: "B" }, { ...cdb, id: "q3", idade_dias: 3, nome: "C" },
  ]);
  setup();
  await screen.findByText("C");
  expect(screen.getByText(/· hoje/)).toBeInTheDocument();
  expect(screen.getByText(/· há 1 dia/)).toBeInTheDocument();
  expect(screen.getByText(/· há 3 dias/)).toBeInTheDocument();
});

test("expirada vai para o fim, em cinza, com selo; o filtro Mostrar expiradas a esconde", async () => {
  mocked.products.list.mockResolvedValue([velha, cdb]);
  const user = userEvent.setup();
  setup();
  await screen.findByText("CDB Banco Alfa");
  const sec = screen.getByRole("region", { name: "Meus produtos" });
  const itens = within(sec).getAllByRole("listitem");
  expect(itens[0]).toHaveTextContent("CDB Banco Alfa");
  expect(itens[1]).toHaveTextContent("CDB Velho");
  expect(within(itens[1]).getByText("expirada")).toBeInTheDocument();
  expect(itens[1].className).toMatch(/opacity|grayscale/);
  const filtro = screen.getByRole("checkbox", { name: "Mostrar expiradas" });
  expect(filtro).toBeChecked();
  await user.click(filtro);
  expect(screen.queryByText("CDB Velho")).toBeNull();
  expect(screen.getByText("CDB Banco Alfa")).toBeInTheDocument();
});

test("editar produto envia disponivel_ate e mostra Registrado em", async () => {
  mocked.products.list.mockResolvedValue([{ ...cdb, data_registro: "2026-11-20", disponivel_ate: "2026-12-10" }]);
  const user = userEvent.setup();
  setup();
  await user.click(await screen.findByRole("button", { name: "Editar CDB Banco Alfa" }));
  const dialog = screen.getByRole("dialog", { name: "Editar produto" });
  expect(within(dialog).getByLabelText("Disponível até")).toHaveValue("2026-12-10");
  expect(within(dialog).getByText("Registrado em 20/11/2026")).toBeInTheDocument();
});
