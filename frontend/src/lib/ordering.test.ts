import { expect, test } from "vitest";
import type { Coverage, SimulationResult } from "../api/types";
import { fixtureResult } from "../test/fixtures";
import { dominados, ordenar } from "./ordering";

interface Opts {
  taxa?: string | null;
  prazo?: number | null;
  valor?: string | null;
  cobertura?: Coverage;
  resgatavel?: boolean;
}

function r(id: string, o: Opts = {}): SimulationResult {
  return {
    ...fixtureResult,
    product: { ...fixtureResult.product, id, nome: id, cobertura: o.cobertura ?? "FGC" },
    resgatavel: o.resgatavel ?? true,
    taxa_liquida_aa: o.taxa === undefined ? "0.1" : o.taxa,
    prazo_saida_dias: o.prazo === undefined ? 0 : o.prazo,
    valor_liquido: o.valor === undefined ? "1000" : o.valor,
  };
}

test("dominância: paga mais e prende menos", () => {
  const a = r("A", { taxa: "0.128", prazo: 730 }), b = r("B", { taxa: "0.125", prazo: 1460 });
  const c = r("C", { taxa: "0.131", prazo: 1460 }), d = r("D", { taxa: "0.128", prazo: 730 });
  expect([...dominados([a, b, c, d])]).toEqual(["B"]); // empate exato A×D não domina
});

test("dominância só sobre a lista recebida (filtrada)", () => {
  const lci = r("LCI", { taxa: "0.11", prazo: 365 }), cdb = r("CDB", { taxa: "0.12", prazo: 365 });
  expect(dominados([lci, cdb]).has("LCI")).toBe(true);
  expect(dominados([lci]).size).toBe(0);
});

test("nulos e não resgatáveis não dominam nem são dominados e vão para o fim", () => {
  const ok = r("ok", { taxa: "0.12", prazo: 0 }), semTaxa = r("semTaxa", { taxa: null, prazo: 0 });
  const preso = r("preso", { taxa: null, prazo: null, resgatavel: false });
  expect(dominados([ok, semTaxa, preso]).size).toBe(0);
  for (const o of ["VALOR_LIQUIDO", "TAXA", "CUSTO_BENEFICIO", "PRAZO", "SEGURANCA"] as const) {
    expect(ordenar([preso, semTaxa, ok], o).map((x) => x.product.id)).toEqual(["ok", "semTaxa", "preso"]);
  }
});

test("custo-benefício forma a escada e manda dominados para o fim", () => {
  const lista = [r("X", { taxa: "0.131", prazo: 1460 }), r("Ruim", { taxa: "0.115", prazo: 900 }),
    r("Y", { taxa: "0.114", prazo: 0 }), r("W", { taxa: "0.123", prazo: 365 })];
  expect(ordenar(lista, "CUSTO_BENEFICIO").map((x) => x.product.id)).toEqual(["Y", "W", "X", "Ruim"]);
});

test("segurança e prazo", () => {
  const t = r("T", { taxa: "0.10", prazo: 3000, cobertura: "TESOURO" }), f = r("F", { taxa: "0.12", prazo: 0, cobertura: "FGC" });
  const n = r("N", { taxa: "0.14", prazo: 30, cobertura: "NENHUMA" });
  expect(ordenar([n, f, t], "SEGURANCA").map((x) => x.product.id)).toEqual(["T", "F", "N"]);
  expect(ordenar([t, n, f], "PRAZO").map((x) => x.product.id)).toEqual(["F", "N", "T"]);
});

test("valor líquido desc, depois taxa desc, depois nome", () => {
  const a = r("a", { valor: "100", taxa: "0.1" }), b = r("b", { valor: "200", taxa: "0.1" });
  const c = r("c", { valor: "200", taxa: "0.2" });
  expect(ordenar([a, b, c], "VALOR_LIQUIDO").map((x) => x.product.id)).toEqual(["c", "b", "a"]);
});

test("não muta a entrada", () => { const l = [r("b", { taxa: "0.1", prazo: 1 }), r("a", { taxa: "0.2", prazo: 1 })];
  const copia = [...l]; ordenar(l, "TAXA"); expect(l).toEqual(copia); });

test("custo-benefício: nulos vão para o fim do bloco resgatável", () => {
  const ok = r("ok", { taxa: "0.12", prazo: 365 }), semTaxa = r("semTaxa", { taxa: null, prazo: 0 });
  expect(ordenar([semTaxa, ok], "CUSTO_BENEFICIO").map((x) => x.product.id)).toEqual(["ok", "semTaxa"]);
  const a = r("A", { taxa: "0.128", prazo: 730 }), nulo = r("nulo", { taxa: "0.10", prazo: null });
  const b = r("B", { taxa: "0.125", prazo: 1460 });
  expect(ordenar([a, nulo, b], "CUSTO_BENEFICIO").map((x) => x.product.id)).toEqual(["A", "B", "nulo"]);
});
