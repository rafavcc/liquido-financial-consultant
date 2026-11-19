import { formatDate } from "./format";

export const FONTE_NOME: Record<string, string> = {
  bcb: "Banco Central",
  focus: "Boletim Focus",
  tesouro: "Tesouro Direto",
};

const p2 = (n: number) => String(n).padStart(2, "0");

/** "19/11 14:30", no fuso do navegador. */
export function formatDayMonthTime(iso: string): string {
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return "—";
  return `${p2(d.getDate())}/${p2(d.getMonth() + 1)} ${p2(d.getHours())}:${p2(d.getMinutes())}`;
}

/** Carimbo mais antigo entre as fontes usadas: é o que limita o quão fresco o resultado é. */
export function oldestFetchedAt(fetchedAt: Record<string, string>): string | null {
  const stamps = Object.values(fetchedAt).sort();
  return stamps.length ? stamps[0] : null;
}

/** "Banco Central indisponível (tempo esgotado) — usando dados de 19/11 14:30". */
export function staleMessage(source: string, reason: string, fetchedAt: string | undefined): string {
  const nome = FONTE_NOME[source] ?? source;
  const motivo = reason ? ` (${reason.charAt(0).toLowerCase()}${reason.slice(1)})` : "";
  const dados = fetchedAt ? `usando dados de ${formatDayMonthTime(fetchedAt)}` : "sem dados salvos";
  return `${nome} indisponível${motivo} — ${dados}`;
}

export const refMonth = (iso: string) => `${iso.slice(5, 7)}/${iso.slice(0, 4)}`;
export const vigenteEm = (iso: string) => `em ${formatDate(iso)}`;
