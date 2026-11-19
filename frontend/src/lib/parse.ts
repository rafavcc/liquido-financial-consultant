/**
 * Converte entrada em formato brasileiro para string decimal canônica.
 * Vírgula é o separador decimal; ponto é sempre separador de milhar.
 */
export function parseBRL(input: string): string | null {
  const s = input.replace(/R\$/gi, "").replace(/\s/g, "");
  if (!/^[\d.,]+$/.test(s)) return null;
  const parts = s.split(",");
  if (parts.length > 2) return null;
  const [intRaw, dec] = parts;
  if (!/^\d[\d.]*$/.test(intRaw) && !(intRaw === "" && dec !== undefined)) return null;
  if (/\.\./.test(intRaw) || intRaw.endsWith(".")) return null;
  if (dec !== undefined && !/^\d+$/.test(dec)) return null;
  const int = intRaw.replace(/\./g, "") || "0";
  return dec !== undefined ? `${int}.${dec}` : int;
}
