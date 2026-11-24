import { expect, test } from "vitest";
import { ISENTOS_PADRAO, TIPO_GRUPOS, tipoGrupo } from "./labels";

test("LCD pertence ao grupo LCI/LCA/LCD e é isenta por padrão", () => {
  expect(tipoGrupo("LCD")).toBe("LCI_LCA");
  expect(TIPO_GRUPOS.find((g) => g.id === "LCI_LCA")?.label).toBe("LCI/LCA/LCD");
  expect(ISENTOS_PADRAO).toContain("LCD");
});
