import { render, screen, within } from "@testing-library/react";
import { MarketStrip } from "./MarketStrip";
import { formatDayMonthTime } from "../lib/market";
import { fixtureResponse } from "../test/fixtures";

const OLD = "2026-11-18T09:00:00Z";
const NEW = "2026-11-19T15:30:00Z";
const base = fixtureResponse.mercado;

test("mostra o carimbo MAIS ANTIGO entre as fontes, não o mais recente", () => {
  const m = { ...base, fetched_at: { bcb: NEW, focus: OLD, tesouro: NEW } };
  render(<MarketStrip mercado={m} refreshing={false} onRefresh={() => {}} />);
  expect(screen.getAllByText(`Atualizado em ${formatDayMonthTime(OLD)}`).length).toBeGreaterThan(0);
  expect(screen.queryByText(`Atualizado em ${formatDayMonthTime(NEW)}`)).toBeNull();
});

test("falha de fonte em pt-BR com a data dos dados em uso, sem texto cru de exceção", () => {
  const m = { ...base, fetched_at: { bcb: OLD, focus: NEW }, errors: { bcb: "Sem conexão com a fonte", tesouro: "Tempo esgotado" } };
  render(<MarketStrip mercado={m} refreshing={false} onRefresh={() => {}} />);
  const alerts = screen.getAllByRole("alert").map((a) => a.textContent);
  expect(alerts).toContain(`Banco Central indisponível (sem conexão com a fonte) — usando dados de ${formatDayMonthTime(OLD)}`);
  expect(alerts).toContain("Tesouro Direto indisponível (tempo esgotado) — sem dados salvos");
});

test("cartões mostram a data dos dados em uso e o detalhe lista cada fonte", () => {
  const m = { ...base, fetched_at: { bcb: OLD, tesouro: NEW }, tesouro_data_base: "2026-11-18" };
  render(<MarketStrip mercado={m} refreshing={false} onRefresh={() => {}} />);
  expect(screen.getAllByText("em 05/11/2026")).toHaveLength(2); // Selic e CDI
  expect(screen.getByText("ref. 10/2026")).toBeInTheDocument();
  const detalhes = screen.getByText("Dados por fonte").closest("details")!;
  expect(within(detalhes).getByText(`Banco Central: ${formatDayMonthTime(OLD)}`)).toBeInTheDocument();
  expect(within(detalhes).getByText("Preços do Tesouro de 18/11/2026")).toBeInTheDocument();
});
