import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { api, ApiError } from "../api/client";
import { fixtureResult } from "../test/fixtures";
import { ProductForm } from "./ProductForm";

vi.mock("../api/client", async (orig) => {
  const real = await orig<typeof import("../api/client")>();
  return {
    ...real,
    api: { products: { create: vi.fn(), update: vi.fn() } },
  };
});

const mocked = vi.mocked(api, true);

function setup(props: Partial<React.ComponentProps<typeof ProductForm>> = {}) {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  const invalidate = vi.spyOn(qc, "invalidateQueries");
  const onOpenChange = vi.fn();
  render(
    <QueryClientProvider client={qc}>
      <ProductForm open onOpenChange={onOpenChange} {...props} />
    </QueryClientProvider>,
  );
  return { invalidate, onOpenChange };
}

async function preencheBasico(user: ReturnType<typeof userEvent.setup>) {
  await user.type(screen.getByLabelText("Nome"), "CDB Teste");
  await user.type(screen.getByLabelText("Emissor"), "Banco Teste");
  await user.type(screen.getByLabelText("Plataforma"), "XP");
  fireEvent.change(screen.getByLabelText("Vencimento"), { target: { value: "2029-05-10" } });
}

beforeEach(() => {
  mocked.products.create.mockReset();
  mocked.products.update.mockReset();
  mocked.products.create.mockResolvedValue(fixtureResult.product);
  mocked.products.update.mockResolvedValue(fixtureResult.product);
});

test("FUNDO_RF mostra Taxa de administração e esconde Vencimento e Liquidez", async () => {
  const user = userEvent.setup();
  setup();
  expect(screen.getByLabelText("Vencimento")).toBeInTheDocument();
  expect(screen.queryByLabelText("Taxa de administração")).toBeNull();
  await user.selectOptions(screen.getByLabelText("Tipo"), "FUNDO_RF");
  expect(screen.getByLabelText("Taxa de administração")).toBeInTheDocument();
  expect(screen.getByLabelText("Prazo de resgate")).toBeInTheDocument();
  expect(screen.getByLabelText("Classe tributária")).toBeInTheDocument();
  expect(screen.queryByLabelText("Vencimento")).toBeNull();
  expect(screen.queryByLabelText("Liquidez")).toBeNull();
  const idx = screen.getByLabelText("Indexador") as HTMLSelectElement;
  expect(within(idx).getAllByRole("option").map((o) => o.textContent)).toEqual(["% do CDI", "CDI +"]);
});

test("PCT_CDI com 112 envia taxa \"1.12\"", async () => {
  const user = userEvent.setup();
  setup();
  await preencheBasico(user);
  await user.selectOptions(screen.getByLabelText("Indexador"), "PCT_CDI");
  await user.type(screen.getByLabelText("Taxa"), "112");
  await user.click(screen.getByRole("button", { name: "Salvar" }));
  await waitFor(() => expect(mocked.products.create).toHaveBeenCalledTimes(1));
  const body = mocked.products.create.mock.calls[0][0];
  expect(body).toMatchObject({
    tipo: "CDB", nome: "CDB Teste", emissor: "Banco Teste", plataforma: "XP", indexador: "PCT_CDI",
    taxa: "1.12", data_vencimento: "2029-05-10", valor_minimo: "0", liquidez: "NO_VENCIMENTO",
    taxa_adm: null, prazo_resgate_dias: null, classe_tributaria: null, data_carencia: null,
  });
  expect(body).not.toHaveProperty("id");
});

test("PRE com 14,2 envia \"0.142\"", async () => {
  const user = userEvent.setup();
  setup();
  await preencheBasico(user);
  await user.selectOptions(screen.getByLabelText("Indexador"), "PRE");
  await user.type(screen.getByLabelText("Taxa"), "14,2");
  await user.type(screen.getByLabelText("Valor mínimo"), "1000");
  await user.click(screen.getByRole("button", { name: "Salvar" }));
  await waitFor(() => expect(mocked.products.create).toHaveBeenCalled());
  expect(mocked.products.create.mock.calls[0][0]).toMatchObject({ taxa: "0.142", valor_minimo: "1000" });
});

test("rótulo e sufixo da taxa mudam por indexador", async () => {
  const user = userEvent.setup();
  setup();
  expect(screen.getByText("% do CDI", { selector: "span" })).toBeInTheDocument();
  await user.selectOptions(screen.getByLabelText("Indexador"), "IPCA_MAIS");
  expect(screen.getByText("IPCA +", { selector: "span" })).toBeInTheDocument();
  expect(screen.getByText("% a.a.", { selector: "span" })).toBeInTheDocument();
});

test("LCI não oferece liquidez Diária; CDB oferece", async () => {
  const user = userEvent.setup();
  setup();
  const liq = () => within(screen.getByLabelText("Liquidez")).getAllByRole("option").map((o) => o.textContent);
  expect(liq()).toContain("Diária");
  await user.selectOptions(screen.getByLabelText("Tipo"), "LCI");
  expect(liq()).toEqual(["No vencimento", "Diária após carência"]);
});

test("trocar para LCI com liquidez Diária volta para No vencimento", async () => {
  const user = userEvent.setup();
  setup();
  await user.selectOptions(screen.getByLabelText("Liquidez"), "DIARIA");
  await user.selectOptions(screen.getByLabelText("Tipo"), "LCI");
  expect(screen.getByLabelText("Liquidez")).toHaveValue("NO_VENCIMENTO");
});

test("Diária após carência mostra Data de carência", async () => {
  const user = userEvent.setup();
  setup();
  expect(screen.queryByLabelText("Data de carência")).toBeNull();
  await user.selectOptions(screen.getByLabelText("Liquidez"), "DIARIA_APOS_CARENCIA");
  expect(screen.getByLabelText("Data de carência")).toBeInTheDocument();
});

test("Fundo envia liquidez DIARIA, vencimento nulo e campos do fundo", async () => {
  const user = userEvent.setup();
  setup();
  await user.selectOptions(screen.getByLabelText("Tipo"), "FUNDO_RF");
  await user.type(screen.getByLabelText("Nome"), "Fundo X");
  await user.type(screen.getByLabelText("Emissor"), "Gestora Y");
  await user.type(screen.getByLabelText("Plataforma"), "BTG Pactual");
  await user.type(screen.getByLabelText("Taxa"), "105");
  await user.type(screen.getByLabelText("Taxa de administração"), "0,30");
  await user.type(screen.getByLabelText("Prazo de resgate"), "1");
  await user.selectOptions(screen.getByLabelText("Classe tributária"), "CURTO");
  await user.click(screen.getByRole("button", { name: "Salvar" }));
  await waitFor(() => expect(mocked.products.create).toHaveBeenCalled());
  expect(mocked.products.create.mock.calls[0][0]).toMatchObject({
    tipo: "FUNDO_RF", liquidez: "DIARIA", data_vencimento: null, data_carencia: null, taxa: "1.05",
    taxa_adm: "0.003", prazo_resgate_dias: 1, classe_tributaria: "CURTO", indexador: "PCT_CDI",
  });
});

test("resposta 422 mostra mensagens no topo e junto ao campo", async () => {
  const user = userEvent.setup();
  mocked.products.create.mockRejectedValue(
    new ApiError(422, ["LCI exige carência mínima de 12 meses", "taxa: valor fora do intervalo"]),
  );
  setup();
  await preencheBasico(user);
  await user.type(screen.getByLabelText("Taxa"), "112");
  await user.click(screen.getByRole("button", { name: "Salvar" }));
  const alert = await screen.findByRole("alert");
  expect(within(alert).getByText("LCI exige carência mínima de 12 meses")).toBeInTheDocument();
  expect(within(alert).getByText("taxa: valor fora do intervalo")).toBeInTheDocument();
  expect(screen.getByText("valor fora do intervalo", { selector: "p" })).toBeInTheDocument();
});

test("campos obrigatórios vazios não chamam a API", async () => {
  const user = userEvent.setup();
  setup();
  await user.click(screen.getByRole("button", { name: "Salvar" }));
  expect(mocked.products.create).not.toHaveBeenCalled();
  expect(screen.getAllByText("Campo obrigatório").length).toBeGreaterThan(0);
});

test("sucesso fecha o formulário e invalida produtos e simulação", async () => {
  const user = userEvent.setup();
  const { invalidate, onOpenChange } = setup();
  await preencheBasico(user);
  await user.type(screen.getByLabelText("Taxa"), "112");
  await user.click(screen.getByRole("button", { name: "Salvar" }));
  await waitFor(() => expect(onOpenChange).toHaveBeenCalledWith(false));
  const keys = invalidate.mock.calls.map((c) => (c[0] as { queryKey: unknown[] }).queryKey[0]);
  expect(keys).toEqual(expect.arrayContaining(["products", "simulate"]));
});

test("edição preenche o formulário em %, e envia PUT com o id", async () => {
  const user = userEvent.setup();
  setup({ product: { ...fixtureResult.product, id: "abc", taxa: "1.12", valor_minimo: "1000.00", ativo: false, exemplo: true } });
  expect(screen.getByRole("heading", { name: "Editar produto" })).toBeInTheDocument();
  expect(screen.getByLabelText("Taxa")).toHaveValue("112");
  expect(screen.getByLabelText("Valor mínimo")).toHaveValue("1.000");
  expect(screen.getByLabelText("Nome")).toHaveValue("CDB Banco Alfa");
  await user.click(screen.getByRole("button", { name: "Salvar" }));
  await waitFor(() => expect(mocked.products.update).toHaveBeenCalled());
  const [id, body] = mocked.products.update.mock.calls[0];
  expect(id).toBe("abc");
  expect(body).toMatchObject({ id: "abc", taxa: "1.12", valor_minimo: "1000.00", ativo: false, exemplo: true });
});

test("edição sem alterar nada reenvia todos os campos idênticos (inclui valor_minimo com 3 casas)", async () => {
  const user = userEvent.setup();
  const original = {
    ...fixtureResult.product, id: "abc", plataforma: "BTG Pactual", emissor: "Banco Z", taxa: "1.125",
    valor_minimo: "1000.505", liquidez: "DIARIA_APOS_CARENCIA" as const, data_carencia: "2027-06-01",
    data_vencimento: "2029-05-10", observacoes: "nota", cobertura: "FGC" as const, ativo: true, exemplo: false,
  };
  setup({ product: original });
  await user.click(screen.getByRole("button", { name: "Salvar" }));
  await waitFor(() => expect(mocked.products.update).toHaveBeenCalled());
  const [, body] = mocked.products.update.mock.calls[0];
  expect(body).toEqual({
    id: "abc", tipo: original.tipo, nome: original.nome, emissor: "Banco Z", plataforma: "BTG Pactual",
    indexador: original.indexador, taxa: "1.125", data_vencimento: "2029-05-10", valor_minimo: "1000.505",
    liquidez: "DIARIA_APOS_CARENCIA", data_carencia: "2027-06-01", cobertura: "FGC", ativo: true, exemplo: false,
    observacoes: "nota", taxa_adm: null, prazo_resgate_dias: null, classe_tributaria: null,
  });
});

test("edição de fundo sem alterar nada reenvia campos do fundo idênticos", async () => {
  const user = userEvent.setup();
  const fundo = {
    ...fixtureResult.product, id: "f1", tipo: "FUNDO_RF" as const, nome: "Fundo X", taxa: "1.05", data_vencimento: null,
    liquidez: "DIARIA" as const, taxa_adm: "0.003", prazo_resgate_dias: 30, classe_tributaria: "CURTO" as const,
    cobertura: "NENHUMA" as const, valor_minimo: "500",
  };
  setup({ product: fundo });
  await user.click(screen.getByRole("button", { name: "Salvar" }));
  await waitFor(() => expect(mocked.products.update).toHaveBeenCalled());
  expect(mocked.products.update.mock.calls[0][1]).toEqual({
    id: "f1", tipo: "FUNDO_RF", nome: "Fundo X", emissor: fundo.emissor, plataforma: fundo.plataforma,
    indexador: fundo.indexador, taxa: "1.05", data_vencimento: null, valor_minimo: "500", liquidez: "DIARIA",
    data_carencia: null, cobertura: "NENHUMA", ativo: true, exemplo: false, observacoes: fundo.observacoes,
    taxa_adm: "0.003", prazo_resgate_dias: 30, classe_tributaria: "CURTO",
  });
});

test("editar CRI trocando para CDB não envia cobertura (backend deriva)", async () => {
  const user = userEvent.setup();
  setup({ product: { ...fixtureResult.product, id: "c1", tipo: "CRI", cobertura: "NENHUMA" } });
  await user.selectOptions(screen.getByLabelText("Tipo"), "CDB");
  await user.click(screen.getByRole("button", { name: "Salvar" }));
  await waitFor(() => expect(mocked.products.update).toHaveBeenCalled());
  const body = mocked.products.update.mock.calls[0][1];
  expect(body.tipo).toBe("CDB");
  expect(body).not.toHaveProperty("cobertura");
});

test("trocar o tipo limpa erros do topo e dos campos", async () => {
  const user = userEvent.setup();
  mocked.products.create.mockRejectedValue(new ApiError(422, ["taxa: inválida"]));
  setup();
  await preencheBasico(user);
  await user.type(screen.getByLabelText("Taxa"), "112");
  await user.click(screen.getByRole("button", { name: "Salvar" }));
  await screen.findByRole("alert");
  await user.selectOptions(screen.getByLabelText("Tipo"), "LCA");
  expect(screen.queryByRole("alert")).toBeNull();
  expect(screen.queryByText("inválida")).toBeNull();
});
