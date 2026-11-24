import { expect, test } from "vitest";
import type { SimulationResult } from "../api/types";
import { fixtureResult } from "../test/fixtures";
import { ALERT_META, HORIZONTES, ISENTOS_PADRAO, ORDENACOES, TIPO_GRUPOS, prazoSaidaLabel, tipoGrupo } from "./labels";

test("LCD pertence ao grupo LCI/LCA/LCD e é isenta por padrão", () => {
  expect(tipoGrupo("LCD")).toBe("LCI_LCA");
  expect(TIPO_GRUPOS.find((g) => g.id === "LCI_LCA")?.label).toBe("LCI/LCA/LCD");
  expect(ISENTOS_PADRAO).toContain("LCD");
});

test("alertas de oferta antiga e importado por IA", () => {
  expect(ALERT_META.OFERTA_ANTIGA).toEqual({ icon: "⏳", text: "Oferta antiga", tone: "warn" });
  expect(ALERT_META.IMPORTADO_IA).toEqual({ icon: "🤖", text: "Importado por IA", tone: "off" });
});

const base = fixtureResult;
const res = (p: Partial<SimulationResult["product"]>, prazo: number | null = 100): SimulationResult =>
  ({ ...base, prazo_saida_dias: prazo, product: { ...base.product, ...p } });

test("prazoSaidaLabel", () => {
  const hoje = "2026-11-19";
  expect(prazoSaidaLabel(res({}, null), hoje)).toBeNull();
  expect(prazoSaidaLabel(res({ tipo: "FUNDO_RF", prazo_resgate_dias: 30 }), hoje)).toBe("D+30");
  expect(prazoSaidaLabel(res({ tipo: "FUNDO_RF", prazo_resgate_dias: 0 }), hoje)).toBe("Liquidez diária");
  expect(prazoSaidaLabel(res({ tipo: "FUNDO_RF", prazo_resgate_dias: null }), hoje)).toBe("Liquidez diária");
  expect(prazoSaidaLabel(res({ tipo: "TESOURO_SELIC", data_vencimento: "2031-03-01" }), hoje)).toBe("Liquidez diária");
  expect(prazoSaidaLabel(res({ liquidez: "DIARIA" }), hoje)).toBe("Liquidez diária");
  expect(prazoSaidaLabel(res({ liquidez: "DIARIA_APOS_CARENCIA", data_carencia: "2027-05-19" }), hoje)).toBe("Carência até 19/05/2027");
  expect(prazoSaidaLabel(res({ liquidez: "DIARIA_APOS_CARENCIA", data_carencia: "2026-01-10" }), hoje)).toBe("Liquidez diária");
  expect(prazoSaidaLabel(res({ tipo: "TESOURO_IPCA", data_vencimento: "2035-05-15" }), hoje)).toBe("Venda antes de 15/05/2035 a preço de mercado");
  expect(prazoSaidaLabel(res({ liquidez: "NO_VENCIMENTO", data_vencimento: "2028-11-16" }), hoje)).toBe("Preso até 16/11/2028");
});

test("ORDENACOES e HORIZONTES", () => {
  expect(ORDENACOES.map((o) => o.label)).toEqual(["Valor líquido", "Taxa líquida a.a.", "Custo-benefício", "Menor prazo de saída", "Segurança"]);
  expect(HORIZONTES.map((h) => h.label)).toEqual(["Sem data", "1 ano", "2 anos", "Escolher data"]);
});
