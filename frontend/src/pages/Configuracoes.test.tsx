import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { api, ApiError } from "../api/client";
import type { Settings } from "../api/types";
import { fixtureMercadoProjecao } from "../test/fixtures";
import { Configuracoes } from "./Configuracoes";

vi.mock("../api/client", async (orig) => {
  const real = await orig<typeof import("../api/client")>();
  return {
    ...real,
    api: {
      market: vi.fn(),
      refreshMarket: vi.fn(),
      settings: { get: vi.fn(), update: vi.fn(), reset: vi.fn() },
    },
  };
});
const mocked = vi.mocked(api, true);

const settings: Settings = {
  ir_brackets: [
    { max_days: 180, rate: "0.225" },
    { max_days: 360, rate: "0.20" },
    { max_days: 720, rate: "0.175" },
    { max_days: null, rate: "0.15" },
  ],
  iof_table: ["0.96", "0.93", "0.90", "0.86", "0.83", "0.80", "0.76", "0.73", "0.70", "0.66", "0.63", "0.60", "0.56", "0.53", "0.50",
    "0.46", "0.43", "0.40", "0.36", "0.33", "0.30", "0.26", "0.23", "0.20", "0.16", "0.13", "0.10", "0.06", "0.03"],
  ir_exempt_types: ["CRA", "LCI", "LCA", "CRI"],
  iof_exempt_types: ["CRA", "LCI", "LCA", "CRI"],
  come_cotas_longo: "0.15",
  come_cotas_curto: "0.20",
  ir_fundo_curto_ate_180: "0.225",
  ir_fundo_curto_acima_180: "0.20",
  custodia_b3_aa: "0.0020",
  tesouro_selic_isencao_custodia: "10000",
  spread_cdi_selic: "0.0010",
  projection_mode: "focus",
  manual_selic_by_year: {},
  manual_ipca_by_year: {},
  market_cache_ttl_hours: 6,
  fgc_limite: "250000",
  prazo_min_meses_lci: 6,
  prazo_min_meses_lci_ipca: 36,
  prazo_min_meses_lca: 6,
  prazo_min_meses_lca_ipca: 12,
  prazo_min_meses_lcd: 12,
};

function setup() {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  const invalidate = vi.spyOn(qc, "invalidateQueries");
  render(
    <QueryClientProvider client={qc}>
      <Configuracoes />
    </QueryClientProvider>,
  );
  return { invalidate };
}

const salvar = () => screen.getByRole("button", { name: "Salvar alterações" });
const semBarra = () => expect(screen.queryByRole("button", { name: "Salvar alterações" })).toBeNull();

beforeEach(() => {
  vi.clearAllMocks();
  mocked.settings.get.mockResolvedValue(settings);
  mocked.settings.update.mockImplementation(async (s) => s);
  mocked.settings.reset.mockResolvedValue(settings);
  mocked.market.mockResolvedValue({
    ...fixtureMercadoProjecao,
    fetched_at: { bcb: "2026-11-19T15:50:03Z", focus: "2026-11-19T15:50:03Z", tesouro: "2026-11-19T15:50:03Z" },
    errors: { focus: "Tempo esgotado" },
  });
  mocked.refreshMarket.mockResolvedValue(fixtureMercadoProjecao);
});

test("a barra de salvar só existe quando há alterações", async () => {
  setup();
  const campo = await screen.findByLabelText("Custódia B3 (% ao ano)");
  semBarra();
  expect(screen.queryByText(/Você tem alterações/)).toBeNull();
  await userEvent.type(campo, "1");
  expect(salvar()).toBeEnabled();
  expect(screen.getByText(/Você tem alterações/)).toBeInTheDocument();
  await userEvent.clear(campo);
  await userEvent.type(campo, "0,2");
  semBarra();
});

test("editar a custódia para 0,25 envia fração 0.0025 e preserva os demais campos byte a byte", async () => {
  const { invalidate } = setup();
  const campo = await screen.findByLabelText("Custódia B3 (% ao ano)");
  expect(campo).toHaveValue("0,2");
  await userEvent.clear(campo);
  await userEvent.type(campo, "0,25");
  expect(salvar()).toBeEnabled();
  await userEvent.click(salvar());
  await waitFor(() => expect(mocked.settings.update).toHaveBeenCalled());
  expect(mocked.settings.update.mock.calls[0][0]).toEqual({ ...settings, custodia_b3_aa: "0.0025" });
  const keys = ["settings", "simulate", "market"];
  await waitFor(() => {
    for (const k of keys) expect(invalidate).toHaveBeenCalledWith({ queryKey: [k] });
  });
  await waitFor(semBarra);
});

test("editar alíquota e limite de dias da tabela de IR", async () => {
  setup();
  const rate = await screen.findByLabelText("Alíquota de IR até 180 dias");
  expect(rate).toHaveValue("22,5");
  await userEvent.clear(rate);
  await userEvent.type(rate, "22");
  const dias = screen.getByLabelText("Limite da faixa 2 de IR (dias)");
  await userEvent.clear(dias);
  await userEvent.type(dias, "365");
  expect(screen.getByText("Acima de 720 dias")).toBeInTheDocument();
  await userEvent.click(salvar());
  await waitFor(() => expect(mocked.settings.update).toHaveBeenCalled());
  const sent = mocked.settings.update.mock.calls[0][0];
  expect(sent.ir_brackets).toEqual([
    { max_days: 180, rate: "0.22" },
    { max_days: 365, rate: "0.20" },
    { max_days: 720, rate: "0.175" },
    { max_days: null, rate: "0.15" },
  ]);
});

test("tabela de IOF recolhida por padrão e editável", async () => {
  setup();
  await screen.findByLabelText("Custódia B3 (% ao ano)");
  expect(screen.queryByLabelText("IOF no dia 1")).toBeNull();
  await userEvent.click(screen.getByRole("button", { name: /Tabela de IOF/ }));
  const d1 = screen.getByLabelText("IOF no dia 1");
  expect(d1).toHaveValue("96");
  expect(screen.getByLabelText("IOF no dia 29")).toHaveValue("3");
  await userEvent.clear(d1);
  await userEvent.type(d1, "95");
  await userEvent.click(salvar());
  await waitFor(() => expect(mocked.settings.update).toHaveBeenCalled());
  const iof = mocked.settings.update.mock.calls[0][0].iof_table;
  expect(iof).toHaveLength(29);
  expect(iof[0]).toBe("0.95");
  expect(iof[1]).toBe("0.93");
});

test("isenções: grupo Tesouro marca todos os TESOURO_* juntos", async () => {
  setup();
  const ir = await screen.findByRole("group", { name: "Isentos de IR" });
  expect(within(ir).getByLabelText("LCI")).toBeChecked();
  expect(within(ir).getByLabelText("CDB")).not.toBeChecked();
  await userEvent.click(within(ir).getByLabelText("Tesouro Direto"));
  await userEvent.click(within(ir).getByLabelText("LCI"));
  await userEvent.click(salvar());
  await waitFor(() => expect(mocked.settings.update).toHaveBeenCalled());
  const sent = mocked.settings.update.mock.calls[0][0];
  expect([...sent.ir_exempt_types].sort()).toEqual(
    ["CRA", "CRI", "LCA", "TESOURO_EDUCA_MAIS", "TESOURO_IPCA", "TESOURO_IPCA_JUROS", "TESOURO_PREFIXADO",
      "TESOURO_PREFIXADO_JUROS", "TESOURO_RENDA_MAIS", "TESOURO_SELIC"].sort(),
  );
  expect(sent.iof_exempt_types).toEqual(settings.iof_exempt_types);
});

test("campos em reais e spread em pontos percentuais", async () => {
  setup();
  const iso = await screen.findByLabelText("Isenção de custódia do Tesouro Selic (R$)");
  expect(iso).toHaveValue("10.000");
  expect(screen.getByLabelText("Spread do CDI sobre a Selic (p.p.)")).toHaveValue("0,1");
  const fgc = screen.getByLabelText("Limite do FGC por instituição (R$)");
  await userEvent.clear(fgc);
  await userEvent.type(fgc, "300000");
  const spread = screen.getByLabelText("Spread do CDI sobre a Selic (p.p.)");
  await userEvent.clear(spread);
  await userEvent.type(spread, "0,15");
  await userEvent.click(salvar());
  await waitFor(() => expect(mocked.settings.update).toHaveBeenCalled());
  const sent = mocked.settings.update.mock.calls[0][0];
  expect(sent.fgc_limite).toBe("300000");
  expect(sent.spread_cdi_selic).toBe("0.0015");
  expect(sent.tesouro_selic_isencao_custodia).toBe("10000");
});

test("modo Manual exibe a tabela de anos e envia Selic/IPCA como fração", async () => {
  setup();
  expect(screen.queryByLabelText("Ano 1")).toBeNull();
  await userEvent.click(await screen.findByRole("radio", { name: "Manual" }));
  const ano = await screen.findByLabelText("Ano da linha 1");
  await userEvent.clear(ano);
  await userEvent.type(ano, "2027");
  await userEvent.type(screen.getByLabelText("Selic no fim de 2027 (%)"), "12,75");
  await userEvent.type(screen.getByLabelText("IPCA em 2027 (%)"), "4,5");
  await userEvent.click(screen.getByRole("button", { name: "Adicionar ano" }));
  expect(screen.getByLabelText("Ano da linha 2")).toBeInTheDocument();
  await userEvent.click(screen.getByRole("button", { name: "Remover linha 2" }));
  expect(screen.queryByLabelText("Ano da linha 2")).toBeNull();
  await userEvent.click(salvar());
  await waitFor(() => expect(mocked.settings.update).toHaveBeenCalled());
  const sent = mocked.settings.update.mock.calls[0][0];
  expect(sent.projection_mode).toBe("manual");
  expect(sent.manual_selic_by_year).toEqual({ "2027": "0.1275" });
  expect(sent.manual_ipca_by_year).toEqual({ "2027": "0.045" });
});

test("modo Manual com linha incompleta bloqueia o salvamento", async () => {
  setup();
  await userEvent.click(await screen.findByRole("radio", { name: "Manual" }));
  expect(await screen.findByLabelText("Ano da linha 1")).toBeInTheDocument();
  expect(salvar()).toBeDisabled();
});

test("erro 422 do backend aparece no topo e junto do grupo", async () => {
  mocked.settings.update.mockRejectedValue(new ApiError(422, ["ir_brackets.1.max_days: deve ser maior que a faixa anterior"]));
  setup();
  const campo = await screen.findByLabelText("Custódia B3 (% ao ano)");
  await userEvent.type(campo, "1");
  await userEvent.click(salvar());
  const alerts = await screen.findAllByText(/deve ser maior que a faixa anterior/);
  expect(alerts.length).toBeGreaterThanOrEqual(2);
  expect(within(screen.getByRole("alert", { name: "Erros ao salvar" })).getByText(/Faixa 2 de IR/)).toBeInTheDocument();
  expect(salvar()).toBeEnabled();
});

test("Restaurar padrões pede confirmação e chama o reset", async () => {
  const { invalidate } = setup();
  await userEvent.click(await screen.findByRole("button", { name: "Restaurar padrões" }));
  const dlg = await screen.findByRole("dialog");
  expect(within(dlg).getByText(/Restaurar padrões\?/)).toBeInTheDocument();
  expect(mocked.settings.reset).not.toHaveBeenCalled();
  await userEvent.click(within(dlg).getByRole("button", { name: "Restaurar" }));
  await waitFor(() => expect(mocked.settings.reset).toHaveBeenCalled());
  await waitFor(() => expect(invalidate).toHaveBeenCalledWith({ queryKey: ["simulate"] }));
  expect(invalidate).toHaveBeenCalledWith({ queryKey: ["settings"] });
  expect(invalidate).toHaveBeenCalledWith({ queryKey: ["market"] });
});

test("Dados: última atualização por fonte, erro e Atualizar agora", async () => {
  const { invalidate } = setup();
  const dados = await screen.findByRole("region", { name: "Dados" });
  expect(await within(dados).findByText("Banco Central")).toBeInTheDocument();
  expect(within(dados).getByText("Focus")).toBeInTheDocument();
  expect(within(dados).getByText("Tesouro Direto")).toBeInTheDocument();
  expect(within(dados).getByText(/Tempo esgotado/)).toBeInTheDocument();
  expect(within(dados).getByLabelText("Validade dos dados em cache (horas)")).toHaveValue("6");
  await userEvent.click(within(dados).getByRole("button", { name: "Atualizar agora" }));
  await waitFor(() => expect(mocked.refreshMarket).toHaveBeenCalled());
  await waitFor(() => expect(invalidate).toHaveBeenCalledWith({ queryKey: ["market"] }));
  expect(invalidate).toHaveBeenCalledWith({ queryKey: ["simulate"] });
});

test("modo Manual: explica a regra da última linha e não deixa removê-la", async () => {
  setup();
  await userEvent.click(await screen.findByRole("radio", { name: "Manual" }));
  const remover = await screen.findByRole("button", { name: "Remover linha 1" });
  expect(remover).toBeDisabled();
  expect(remover).toHaveAttribute("title", "Informe ao menos um ano");
  expect(screen.getByText("É preciso manter ao menos um ano na tabela.")).toBeInTheDocument();
  await userEvent.click(screen.getByRole("button", { name: "Adicionar ano" }));
  expect(screen.getByRole("button", { name: "Remover linha 1" })).toBeEnabled();
});

test("falha ao carregar o status do mercado mostra alerta na seção Dados", async () => {
  mocked.market.mockRejectedValue(new ApiError(500, ["Erro 500"]));
  setup();
  const dados = await screen.findByRole("region", { name: "Dados" });
  expect(await within(dados).findByText(/Não foi possível carregar o status dos dados de mercado/)).toBeInTheDocument();
});

test("falha no refresh ou no reset não aparece como erro de salvamento", async () => {
  mocked.refreshMarket.mockRejectedValue(new ApiError(502, ["Fonte fora do ar"]));
  mocked.settings.reset.mockRejectedValue(new ApiError(500, ["Falha ao restaurar"]));
  setup();
  const dados = await screen.findByRole("region", { name: "Dados" });
  await userEvent.click(within(dados).getByRole("button", { name: "Atualizar agora" }));
  const alerta = await screen.findByRole("alert", { name: "Erro na operação" });
  expect(within(alerta).getByText("Fonte fora do ar")).toBeInTheDocument();
  await userEvent.click(screen.getByRole("button", { name: "Restaurar padrões" }));
  await userEvent.click(within(await screen.findByRole("dialog")).getByRole("button", { name: "Restaurar" }));
  expect(await screen.findByText("Falha ao restaurar")).toBeInTheDocument();
  expect(screen.queryByRole("alert", { name: "Erros ao salvar" })).toBeNull();
  expect(screen.queryByText(/Não foi possível salvar/)).toBeNull();
});

test("modo manual salvo sem nenhum ano mostra a mensagem sob a tabela", async () => {
  mocked.settings.get.mockResolvedValue({ ...settings, projection_mode: "manual" });
  setup();
  const campo = await screen.findByLabelText("Custódia B3 (% ao ano)");
  await userEvent.type(campo, "1");
  const grupo = screen.getByRole("region", { name: "Projeções" });
  expect(within(grupo).getByText("Informe ao menos um ano")).toBeInTheDocument();
  expect(salvar()).toBeDisabled();
});

test("editar um campo limpa o erro de refresh", async () => {
  mocked.refreshMarket.mockRejectedValue(new ApiError(502, ["Fonte fora do ar"]));
  setup();
  const dados = await screen.findByRole("region", { name: "Dados" });
  await userEvent.click(within(dados).getByRole("button", { name: "Atualizar agora" }));
  await screen.findByText("Fonte fora do ar");
  await userEvent.type(screen.getByLabelText("Custódia B3 (% ao ano)"), "1");
  expect(screen.queryByText("Fonte fora do ar")).toBeNull();
});

test("IR de fundo de curto prazo é editável e enviado como fração", async () => {
  setup();
  const acima = await screen.findByLabelText(/IR de fundo de curto prazo, acima de 180 dias/);
  expect(acima).toHaveValue("20");
  expect(screen.getByLabelText(/IR de fundo de curto prazo, até 180 dias/)).toHaveValue("22,5");
  await userEvent.clear(acima);
  await userEvent.type(acima, "21");
  await userEvent.click(salvar());
  await waitFor(() => expect(mocked.settings.update).toHaveBeenCalled());
  const sent = mocked.settings.update.mock.calls[0][0];
  expect(sent.ir_fundo_curto_acima_180).toBe("0.21");
  expect(sent.ir_fundo_curto_ate_180).toBe("0.225");
});

test("prazos mínimos por indexação aparecem e salvar envia o novo valor", async () => {
  setup();
  expect(await screen.findByLabelText("LCI (meses)")).toHaveValue("6");
  expect(screen.getByLabelText("LCI IPCA+ (meses)")).toHaveValue("36");
  expect(screen.getByLabelText("LCA (meses)")).toHaveValue("6");
  expect(screen.getByLabelText("LCA IPCA+ (meses)")).toHaveValue("12");
  expect(screen.getByLabelText("LCD (meses)")).toHaveValue("12");
  const campo = screen.getByLabelText("LCI IPCA+ (meses)");
  await userEvent.clear(campo);
  await userEvent.type(campo, "24");
  await userEvent.click(salvar());
  await waitFor(() => expect(mocked.settings.update).toHaveBeenCalled());
  expect(mocked.settings.update.mock.calls[0][0]).toEqual({ ...settings, prazo_min_meses_lci_ipca: 24 });
});

test("LCD aparece entre os isentos de IR", async () => {
  setup();
  const ir = await screen.findByRole("group", { name: /IR/ });
  expect(within(ir).getByLabelText("LCD")).toBeInTheDocument();
});
