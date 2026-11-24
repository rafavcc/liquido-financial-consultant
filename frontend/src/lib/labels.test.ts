import { expect, test } from "vitest";
import { ALERT_META, ISENTOS_PADRAO, TIPO_GRUPOS, tipoGrupo } from "./labels";

test("LCD pertence ao grupo LCI/LCA/LCD e é isenta por padrão", () => {
  expect(tipoGrupo("LCD")).toBe("LCI_LCA");
  expect(TIPO_GRUPOS.find((g) => g.id === "LCI_LCA")?.label).toBe("LCI/LCA/LCD");
  expect(ISENTOS_PADRAO).toContain("LCD");
});

test("alertas de oferta antiga e importado por IA", () => {
  expect(ALERT_META.OFERTA_ANTIGA).toEqual({ icon: "⏳", text: "Oferta antiga", tone: "warn" });
  expect(ALERT_META.IMPORTADO_IA).toEqual({ icon: "🤖", text: "Importado por IA", tone: "off" });
});
