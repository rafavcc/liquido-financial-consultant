import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { api } from "../api/client";
import type { ImportBatchView, ImportItemView } from "../api/types";
import { Importar } from "./Importar";

vi.mock("../api/client", async (orig) => {
  const real = await orig<typeof import("../api/client")>();
  return { ...real, api: { imports: { status: vi.fn(), upload: vi.fn(), list: vi.fn(), retry: vi.fn() } } };
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

test("repete a consulta enquanto há pendentes, para ao concluir e invalida o ranking", async () => {
  imports.list
    .mockResolvedValueOnce([lote([item({ status: "LENDO" })])])
    .mockResolvedValue([lote([item({ criados: 2 })])]);
  const { invalidate } = setup();
  expect(await screen.findByText("lendo…")).toBeInTheDocument();
  expect(invalidate).not.toHaveBeenCalledWith({ queryKey: ["products"] });
  expect(await screen.findByText("✓ 2 cadastradas", {}, { timeout: 5000 })).toBeInTheDocument();
  expect(imports.list).toHaveBeenCalledTimes(2);
  expect(invalidate).toHaveBeenCalledWith({ queryKey: ["products"] });
  expect(invalidate).toHaveBeenCalledWith({ queryKey: ["simulate"] });
  await new Promise((r) => setTimeout(r, 3300));
  expect(imports.list).toHaveBeenCalledTimes(2);
}, 15000);
