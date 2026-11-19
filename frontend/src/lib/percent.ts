import { maskBRL } from "./format";

/** Desloca a vírgula decimal de uma string numérica em `places` casas (sem float). */
function shift(int: string, frac: string, places: number): string {
  const digits = int + frac;
  const point = int.length + places;
  let i: string;
  let f: string;
  if (point <= 0) {
    i = "0";
    f = "0".repeat(-point) + digits;
  } else if (point >= digits.length) {
    i = digits + "0".repeat(point - digits.length);
    f = "";
  } else {
    i = digits.slice(0, point);
    f = digits.slice(point);
  }
  i = i.replace(/^0+(?=\d)/, "");
  f = f.replace(/0+$/, "");
  return f ? `${i}.${f}` : i;
}

/**
 * Percentual digitado ("14,2", "112") → fração em string decimal ("0.142", "1.12").
 * Aceita vírgula (ou um único ponto) como decimal; sem milhar. Null se inválido.
 */
export function percentToFraction(input: string): string | null {
  const s = input.trim();
  const m = /^(\d+)(?:[,.](\d+))?$/.exec(s);
  if (!m) return null;
  return shift(m[1], m[2] ?? "", -2);
}

/** Fração ("0.142") → percentual para edição ("14,2"). Vazio se ausente/inválido. */
export function fractionToPercent(fraction: string | null | undefined): string {
  if (fraction === null || fraction === undefined) return "";
  const m = /^(\d+)(?:\.(\d+))?$/.exec(fraction.trim());
  if (!m) return "";
  return shift(m[1], m[2] ?? "", 2).replace(".", ",");
}

/** Decimal da API ("1000.50") → texto do campo de valor ("1.000,50"). */
export function decimalToBRLInput(v: string | null | undefined): string {
  if (v === null || v === undefined || v === "") return "";
  const m = /^(\d+)(?:\.(\d+))?$/.exec(v.trim());
  if (!m) return "";
  const frac = (m[2] ?? "").replace(/0+$/, "");
  return maskBRL(frac ? `${m[1]},${frac.padEnd(2, "0")}` : m[1]);
}
