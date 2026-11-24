import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { act, fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { api } from "../api/client";
import type { ImportBatchView, ImportFailureView, ImportItemView } from "../api/types";
import { Importar } from "./Importar";

vi.mock("../api/client", async (orig) => {
  const real = await orig<typeof import("../api/client")>();
  return { ...real, api: { imports: { status: vi.fn(), upload: vi.fn(), list: vi.fn(), retry: vi.fn(), failures: vi.fn(), resolve: vi.fn(), discard: vi.fn() } } };
});
const imports = vi.mocked(api, true).imports;

const item = (o: Partial<ImportItemView>): ImportItemView => ({
  id: "i1", nome_arquivo: "print1.png", print_id: "p1", status: "CONCLUIDO", erro: null,
  criados: 0, renovados: 0, ignorados: 0, falhas: 0, ...o,
});
const lote = (itens: ImportItemView[], id = "b1"): ImportBatchView => ({
  id, criado_em: "2026-11-23T10:00:00", pendentes: itens.filter((i) => i.status === "NA_FILA" || i.status === "LENDO").length, itens,
});
const png = (n: string) => new File(["x"], n, { type: "image/png" });

function setup() {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  const invalidate = vi.spyOn(qc, "invalidateQueries");
  render(
    <QueryClientProvider client={qc}>
      <Importar />
    </QueryClientProvider>,
  );
  return { invalidate };
}

beforeEach(() => {
  vi.resetAllMocks();
  imports.status.mockResolvedValue({ configurado: true, alcancavel: true, modelo: "qwen" });
  imports.list.mockResolvedValue([]);
  imports.failures.mockResolvedValue([]);
});

test("não configurado mostra aviso e desabilita o seletor", async () => {
  imports.status.mockResolvedValue({ configurado: false, alcancavel: null, modelo: null });
  setup();
  expect(await screen.findByText("Importação não configurada")).toBeInTheDocument();
  expect(screen.getByLabelText("Escolher prints")).toBeDisabled();
});

test("envia os 3 arquivos escolhidos e mostra as recusas por nome", async () => {
  imports.upload.mockResolvedValue({ lote: lote([item({})]), recusados: ["doc.pdf: formato não suportado"] });
  setup();
  const input = await screen.findByLabelText("Escolher prints");
  await waitFor(() => expect(input).toBeEnabled());
  const files = [png("a.png"), png("b.png"), png("c.png")];
  await userEvent.upload(input, files);
  await waitFor(() => expect(imports.upload).toHaveBeenCalledWith(files));
  expect(await screen.findByText(/doc\.pdf: formato não suportado/)).toBeInTheDocument();
});

test("mostra o estado de cada item", async () => {
  imports.list.mockResolvedValue([
    lote([
      item({ id: "1", nome_arquivo: "lendo.png", status: "LENDO" }),
      item({ id: "2", nome_arquivo: "ok.png", criados: 4, renovados: 1, falhas: 1 }),
      item({ id: "3", nome_arquivo: "erro.png", status: "ERRO", erro: "Servidor LLM indisponível: timeout" }),
    ]),
  ]);
  imports.retry.mockResolvedValue(item({ id: "3", status: "NA_FILA" }));
  setup();
  expect(await screen.findByText("lendo…")).toBeInTheDocument();
  expect(screen.getByText("✓ 4 cadastradas · 1 renovada")).toBeInTheDocument();
  expect(screen.getByText("⚠ 1 falha")).toBeInTheDocument();
  expect(screen.getByText(/Servidor LLM indisponível: timeout/)).toBeInTheDocument();
  await userEvent.click(screen.getByRole("button", { name: "Tentar de novo" }));
  await waitFor(() => expect(imports.retry).toHaveBeenCalledWith("3"));
});

test("repete a consulta a cada 3000 ms enquanto há pendentes, para ao concluir e invalida o ranking uma vez", async () => {
  vi.useFakeTimers({ shouldAdvanceTime: true });
  try {
    imports.list
      .mockResolvedValueOnce([lote([item({ status: "LENDO" })])])
      .mockResolvedValue([lote([item({ criados: 2 })])]);
    const { invalidate } = setup();
    expect(await screen.findByText("lendo…")).toBeInTheDocument();
    expect(imports.list).toHaveBeenCalledTimes(1);
    await act(async () => {
      await vi.advanceTimersByTimeAsync(2900);
    });
    expect(imports.list).toHaveBeenCalledTimes(1);
    await act(async () => {
      await vi.advanceTimersByTimeAsync(200);
    });
    expect(imports.list).toHaveBeenCalledTimes(2);
    expect(await screen.findByText("✓ 2 cadastradas")).toBeInTheDocument();
    await act(async () => {
      await vi.advanceTimersByTimeAsync(10000);
    });
    expect(imports.list).toHaveBeenCalledTimes(2);
    const chamadas = (k: string) => invalidate.mock.calls.filter(([f]) => JSON.stringify(f?.queryKey) === JSON.stringify([k])).length;
    expect(chamadas("products")).toBe(1);
    expect(chamadas("simulate")).toBe(1);
  } finally {
    vi.useRealTimers();
  }
});

test("falha ao consultar o status explica e mantém o seletor desabilitado", async () => {
  imports.status.mockRejectedValue(new Error("x"));
  setup();
  expect(await screen.findByText("Não foi possível verificar a importação. Tente recarregar a página.")).toBeInTheDocument();
  expect(screen.getByLabelText("Escolher prints")).toBeDisabled();
});

const falha = (o: Partial<ImportFailureView> = {}): ImportFailureView => ({
  id: "f1", item_id: "i1", print_id: "p9", nome_arquivo: "print9.png", erros: ["taxa: campo obrigatório", "data_vencimento: data inválida"],
  parcial: { raw: { tipo: "CDB", emissor: "Banco Beta", nome_exibido: "CDB Beta 2030" }, interpretado: { tipo: "CDB", nome: "CDB Beta 2030", emissor: "Banco Beta", plataforma: "XP", indexador: "PCT_CDI", valor_minimo: "1000" } },
  status: "ABERTA", ...o,
});

test("falhas: lista miniatura do print, erros e ações; sem falhas a seção não aparece", async () => {
  setup();
  await screen.findByText("Nenhum lote importado ainda.");
  expect(screen.queryByRole("region", { name: "Falhas" })).toBeNull();
});

test("falhas: mostra miniatura, erros, Corrigir e Descartar", async () => {
  imports.failures.mockResolvedValue([falha()]);
  setup();
  const sec = await screen.findByRole("region", { name: "Falhas" });
  expect(sec.querySelector('img[src="/api/prints/p9"]')).not.toBeNull();
  expect(within(sec).getByText("taxa: campo obrigatório")).toBeInTheDocument();
  expect(within(sec).getByText("data_vencimento: data inválida")).toBeInTheDocument();
  expect(within(sec).getByRole("button", { name: "Corrigir" })).toBeInTheDocument();
  expect(within(sec).getByRole("button", { name: "Descartar" })).toBeInTheDocument();
});

test("falhas: Corrigir abre o formulário preenchido com o print ao lado e salvar chama resolve", async () => {
  imports.failures.mockResolvedValue([falha()]);
  imports.resolve.mockResolvedValue({} as never);
  const { invalidate } = setup();
  await userEvent.click(await screen.findByRole("button", { name: "Corrigir" }));
  const dialog = await screen.findByRole("dialog", { name: "Corrigir oferta" });
  expect(within(dialog).getByLabelText("Nome")).toHaveValue("CDB Beta 2030");
  expect(within(dialog).getByLabelText("Emissor")).toHaveValue("Banco Beta");
  expect(within(dialog).getByLabelText("Taxa")).toHaveValue("");
  expect(dialog.querySelector('img[src="/api/prints/p9"]')).not.toBeNull();
  await userEvent.type(within(dialog).getByLabelText("Taxa"), "109");
  fireEvent.change(within(dialog).getByLabelText("Vencimento"), { target: { value: "2031-11-18" } });
  await userEvent.click(within(dialog).getByRole("button", { name: "Salvar" }));
  await waitFor(() => expect(imports.resolve).toHaveBeenCalledWith("f1", expect.objectContaining({ nome: "CDB Beta 2030", taxa: "1.09", data_vencimento: "2031-11-18" })));
  await waitFor(() => {
    const keys = invalidate.mock.calls.map((c) => (c[0] as { queryKey: unknown[] }).queryKey[0]);
    expect(keys).toEqual(expect.arrayContaining(["imports", "products", "simulate"]));
  });
});

test("falhas: sem interpretado, o formulário usa o que dá do raw e deixa o resto vazio", async () => {
  imports.failures.mockResolvedValue([falha({ parcial: { raw: { tipo: "LCI", emissor: "Banco Gama", nome_exibido: "LCI Gama" } } })]);
  setup();
  await userEvent.click(await screen.findByRole("button", { name: "Corrigir" }));
  const dialog = await screen.findByRole("dialog", { name: "Corrigir oferta" });
  expect(within(dialog).getByLabelText("Tipo")).toHaveValue("LCI");
  expect(within(dialog).getByLabelText("Nome")).toHaveValue("LCI Gama");
  expect(within(dialog).getByLabelText("Emissor")).toHaveValue("Banco Gama");
  expect(within(dialog).getByLabelText("Plataforma")).toHaveValue("");
  expect(within(dialog).getByLabelText("Taxa")).toHaveValue("");
});

test("falhas: Descartar chama discard e atualiza as listas", async () => {
  imports.failures.mockResolvedValue([falha()]);
  imports.discard.mockResolvedValue(undefined);
  const { invalidate } = setup();
  await userEvent.click(await screen.findByRole("button", { name: "Descartar" }));
  await waitFor(() => expect(imports.discard).toHaveBeenCalledWith("f1"));
  await waitFor(() => {
    const keys = invalidate.mock.calls.map((c) => (c[0] as { queryKey: unknown[] }).queryKey[0]);
    expect(keys).toEqual(expect.arrayContaining(["imports", "products", "simulate"]));
  });
});

test("ao concluir o lote a lista de falhas é invalidada e refeita", async () => {
  vi.useFakeTimers({ shouldAdvanceTime: true });
  try {
    imports.list
      .mockResolvedValueOnce([lote([item({ status: "LENDO" })])])
      .mockResolvedValue([lote([item({ falhas: 1 })])]);
    imports.failures.mockResolvedValueOnce([]).mockResolvedValue([falha()]);
    const { invalidate } = setup();
    expect(await screen.findByText("lendo…")).toBeInTheDocument();
    await act(async () => {
      await vi.advanceTimersByTimeAsync(3100);
    });
    expect(await screen.findByRole("region", { name: "Falhas" })).toBeInTheDocument();
    const keys = invalidate.mock.calls.map((c) => JSON.stringify((c[0] as { queryKey: unknown[] }).queryKey));
    expect(keys).toContain(JSON.stringify(["imports", "failures"]));
  } finally {
    vi.useRealTimers();
  }
});
