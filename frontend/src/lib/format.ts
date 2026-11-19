const brl = new Intl.NumberFormat("pt-BR", { style: "currency", currency: "BRL" });

/** Normaliza espaço não separável (U+00A0 / U+202F) do Intl para espaço comum. */
const plainSpaces = (s: string) => s.replace(/[  ]/g, " ");

export function formatBRL(v: string | null | undefined): string {
  if (v === null || v === undefined || v === "") return "—";
  const n = Number(v);
  if (!Number.isFinite(n)) return "—";
  return plainSpaces(brl.format(n));
}

/** Fração → percentual pt-BR: "0.1365" → "13,65%". */
export function formatPct(fraction: string | null | undefined, digits = 2): string {
  if (fraction === null || fraction === undefined || fraction === "") return "—";
  const n = Number(fraction);
  if (!Number.isFinite(n)) return "—";
  const f = new Intl.NumberFormat("pt-BR", { minimumFractionDigits: digits, maximumFractionDigits: digits });
  return `${f.format(n * 100)}%`;
}

export function formatDate(iso: string | null | undefined): string {
  if (!iso) return "—";
  const [y, m, d] = iso.slice(0, 10).split("-");
  return `${d}/${m}/${y}`;
}

export function formatDateTime(iso: string | null | undefined): string {
  if (!iso) return "—";
  const dt = new Date(iso);
  if (Number.isNaN(dt.getTime())) return "—";
  const date = dt.toLocaleDateString("pt-BR");
  const time = dt.toLocaleTimeString("pt-BR", { hour: "2-digit", minute: "2-digit" });
  return `${date} ${time}`;
}

/** Máscara de digitação: mantém só dígitos e formata como milhar BRL com vírgula opcional. */
export function maskBRL(raw: string): string {
  const cleaned = raw.replace(/[^\d,]/g, "");
  const [intPart, ...rest] = cleaned.split(",");
  const dec = rest.join("").slice(0, 2);
  const int = intPart.replace(/^0+(?=\d)/, "").replace(/\B(?=(\d{3})+(?!\d))/g, ".");
  return rest.length > 0 ? `${int},${dec}` : int;
}
