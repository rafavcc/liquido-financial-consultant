import type { ProductType, Settings } from "../api/types";
import { decimalToBRLInput, fractionToPercent, percentToFraction } from "./percent";
import { parseBRL } from "./parse";

/** Tipos manuais, na ordem em que aparecem nas isenções. */
export const TIPOS_MANUAIS: ProductType[] = ["CDB", "LCI", "LCA", "LCD", "CRI", "CRA", "FUNDO_RF"];
export const TIPOS_TESOURO: ProductType[] = [
  "TESOURO_SELIC", "TESOURO_PREFIXADO", "TESOURO_PREFIXADO_JUROS", "TESOURO_IPCA",
  "TESOURO_IPCA_JUROS", "TESOURO_RENDA_MAIS", "TESOURO_EDUCA_MAIS",
];

export const PRAZOS = [
  { key: "lci", field: "prazo_min_meses_lci", label: "LCI" },
  { key: "lciIpca", field: "prazo_min_meses_lci_ipca", label: "LCI IPCA+" },
  { key: "lca", field: "prazo_min_meses_lca", label: "LCA" },
  { key: "lcaIpca", field: "prazo_min_meses_lca_ipca", label: "LCA IPCA+" },
  { key: "lcd", field: "prazo_min_meses_lcd", label: "LCD" },
] as const;
export type PrazoKey = (typeof PRAZOS)[number]["key"];
export type PrazoField = (typeof PRAZOS)[number]["field"];
export type PrazosForm = Record<PrazoKey, string>;

export interface ManualRow { ano: string; selic: string; ipca: string }

/** Estado editável do formulário: tudo texto, como o usuário digita (percentuais em %, valores em R$). */
export interface SettingsForm {
  ir: { max: string; rate: string }[];
  iof: string[];
  irExempt: ProductType[];
  iofExempt: ProductType[];
  comeLongo: string;
  comeCurto: string;
  irCurtoAte180: string;
  irCurtoAcima180: string;
  custodia: string;
  isencaoSelic: string;
  spread: string;
  mode: "focus" | "manual";
  rows: ManualRow[];
  ttl: string;
  fgc: string;
  prazos: PrazosForm;
  ofertaAlerta: string;
  ofertaExpira: string;
}

export function toForm(s: Settings): SettingsForm {
  const anos = [...new Set([...Object.keys(s.manual_selic_by_year), ...Object.keys(s.manual_ipca_by_year)])].sort();
  return {
    ir: s.ir_brackets.map((b) => ({ max: b.max_days === null ? "" : String(b.max_days), rate: fractionToPercent(b.rate) })),
    iof: s.iof_table.map(fractionToPercent),
    irExempt: [...s.ir_exempt_types],
    iofExempt: [...s.iof_exempt_types],
    comeLongo: fractionToPercent(s.come_cotas_longo),
    comeCurto: fractionToPercent(s.come_cotas_curto),
    irCurtoAte180: fractionToPercent(s.ir_fundo_curto_ate_180),
    irCurtoAcima180: fractionToPercent(s.ir_fundo_curto_acima_180),
    custodia: fractionToPercent(s.custodia_b3_aa),
    isencaoSelic: decimalToBRLInput(s.tesouro_selic_isencao_custodia),
    spread: fractionToPercent(s.spread_cdi_selic),
    mode: s.projection_mode === "manual" ? "manual" : "focus",
    rows: anos.map((a) => ({
      ano: a,
      selic: fractionToPercent(s.manual_selic_by_year[a]),
      ipca: fractionToPercent(s.manual_ipca_by_year[a]),
    })),
    ttl: String(s.market_cache_ttl_hours),
    fgc: decimalToBRLInput(s.fgc_limite),
    prazos: Object.fromEntries(PRAZOS.map((p) => [p.key, String(s[p.field])])) as PrazosForm,
    ofertaAlerta: String(s.oferta_alerta_dias),
    ofertaExpira: String(s.oferta_expira_dias),
  };
}

/** Campo intocado devolve a string original da API (sem arredondar nem reformatar). */
const pct = (text: string, orig: string | undefined): string | null =>
  orig !== undefined && text === fractionToPercent(orig) ? orig : percentToFraction(text);
const money = (text: string, orig: string): string | null =>
  text === decimalToBRLInput(orig) ? orig : parseBRL(text);
const integer = (text: string): number | null => (/^\d+$/.test(text.trim()) ? Number(text.trim()) : null);

const sameSet = (a: ProductType[], b: ProductType[]) => a.length === b.length && a.every((t) => b.includes(t));
const exempt = (now: ProductType[], orig: ProductType[]) => (sameSet(now, orig) ? orig : now);

export interface BuildResult {
  settings: Settings;
  /** Erros locais por caminho no mesmo formato do backend (ex.: "ir_brackets.1.rate"). */
  errors: Record<string, string>;
}

const INVALIDO = "Valor inválido";

export function buildSettings(f: SettingsForm, orig: Settings): BuildResult {
  const errors: Record<string, string> = {};
  const fail = (path: string, msg = INVALIDO) => { errors[path] = msg; };

  const ir_brackets = f.ir.map((row, i) => {
    const o = orig.ir_brackets[i];
    const rate = pct(row.rate, o?.rate);
    if (rate === null) fail(`ir_brackets.${i}.rate`);
    const last = i === f.ir.length - 1;
    let max_days: number | null = null;
    if (!last) {
      max_days = integer(row.max);
      if (max_days === null || max_days < 1) fail(`ir_brackets.${i}.max_days`, "Informe um número de dias inteiro");
    }
    return { max_days, rate: rate ?? "" };
  });
  for (let i = 1; i < f.ir.length - 1; i++) {
    const a = ir_brackets[i - 1].max_days;
    const b = ir_brackets[i].max_days;
    if (a !== null && b !== null && a >= b && !errors[`ir_brackets.${i}.max_days`]) {
      fail(`ir_brackets.${i}.max_days`, "O limite deve ser maior que o da faixa anterior");
    }
  }

  const iof_table = f.iof.map((t, i) => {
    const v = pct(t, orig.iof_table[i]);
    if (v === null) fail(`iof_table.${i}`);
    return v ?? "";
  });

  const rate = (text: string, o: string, path: string) => {
    const v = pct(text, o);
    if (v === null) fail(path);
    return v ?? "";
  };
  const come_cotas_longo = rate(f.comeLongo, orig.come_cotas_longo, "come_cotas_longo");
  const come_cotas_curto = rate(f.comeCurto, orig.come_cotas_curto, "come_cotas_curto");
  const ir_fundo_curto_ate_180 = rate(f.irCurtoAte180, orig.ir_fundo_curto_ate_180, "ir_fundo_curto_ate_180");
  const ir_fundo_curto_acima_180 = rate(f.irCurtoAcima180, orig.ir_fundo_curto_acima_180, "ir_fundo_curto_acima_180");
  const custodia_b3_aa = rate(f.custodia, orig.custodia_b3_aa, "custodia_b3_aa");
  const spread_cdi_selic = rate(f.spread, orig.spread_cdi_selic, "spread_cdi_selic");

  const isencao = money(f.isencaoSelic, orig.tesouro_selic_isencao_custodia);
  if (isencao === null) fail("tesouro_selic_isencao_custodia");
  const fgc = money(f.fgc, orig.fgc_limite);
  if (fgc === null) fail("fgc_limite");
  const ttl = integer(f.ttl);
  if (ttl === null || ttl < 1) fail("market_cache_ttl_hours", "Informe um número de horas inteiro, a partir de 1");

  const prazos = {} as Record<PrazoField, number>;
  for (const p of PRAZOS) {
    const v = integer(f.prazos[p.key]);
    if (v === null) fail(p.field, "Informe um número de meses inteiro, a partir de 0");
    prazos[p.field] = v ?? 0;
  }

  const alerta = integer(f.ofertaAlerta);
  const expira = integer(f.ofertaExpira);
  if (alerta === null || alerta < 1) fail("oferta_alerta_dias", "Informe um número de dias inteiro, a partir de 1");
  if (expira === null || expira < 1) fail("oferta_expira_dias", "Informe um número de dias inteiro, a partir de 1");
  if (alerta !== null && expira !== null && alerta >= 1 && alerta >= expira) fail("oferta_alerta_dias", "O alerta deve vir antes da expiração");

  // Linhas manuais: só bloqueiam o salvamento no modo Manual; no Focus, as originais seguem intactas.
  const rowErrors: Record<string, string> = {};
  const selicMap: Record<string, string> = {};
  const ipcaMap: Record<string, string> = {};
  f.rows.forEach((r, i) => {
    const ano = /^\d{4}$/.test(r.ano.trim()) ? r.ano.trim() : null;
    if (ano === null) rowErrors[`manual_selic_by_year.${i}`] = "Informe o ano com 4 dígitos";
    else if (ano in selicMap) rowErrors[`manual_selic_by_year.${i}`] = `O ano ${ano} aparece mais de uma vez`;
    const selic = pct(r.selic, ano ? orig.manual_selic_by_year[ano] : undefined);
    const ipca = pct(r.ipca, ano ? orig.manual_ipca_by_year[ano] : undefined);
    if (selic === null) rowErrors[`manual_selic_by_year.${i}.selic`] = INVALIDO;
    if (ipca === null) rowErrors[`manual_ipca_by_year.${i}.ipca`] = INVALIDO;
    if (ano !== null && selic !== null && ipca !== null) {
      selicMap[ano] = selic;
      ipcaMap[ano] = ipca;
    }
  });
  const manual = f.mode === "manual";
  if (manual) {
    Object.assign(errors, rowErrors);
    if (f.rows.length === 0) fail("manual_selic_by_year", "Informe ao menos um ano");
  }
  const rowsOk = Object.keys(rowErrors).length === 0;

  const settings: Settings = {
    ...orig,
    ir_brackets,
    iof_table,
    ir_exempt_types: exempt(f.irExempt, orig.ir_exempt_types),
    iof_exempt_types: exempt(f.iofExempt, orig.iof_exempt_types),
    come_cotas_longo,
    come_cotas_curto,
    ir_fundo_curto_ate_180,
    ir_fundo_curto_acima_180,
    custodia_b3_aa,
    tesouro_selic_isencao_custodia: isencao ?? "",
    spread_cdi_selic,
    projection_mode: f.mode,
    manual_selic_by_year: rowsOk ? selicMap : orig.manual_selic_by_year,
    manual_ipca_by_year: rowsOk ? ipcaMap : orig.manual_ipca_by_year,
    market_cache_ttl_hours: ttl ?? 0,
    fgc_limite: fgc ?? "",
    ...prazos,
    oferta_alerta_dias: alerta ?? 0,
    oferta_expira_dias: expira ?? 0,
  };
  return { settings, errors };
}

const sortedMap = (m: Record<string, string>) => Object.entries(m).sort(([a], [b]) => a.localeCompare(b));
const canon = (s: Settings) =>
  JSON.stringify({
    ...s,
    ir_exempt_types: [...s.ir_exempt_types].sort(),
    iof_exempt_types: [...s.iof_exempt_types].sort(),
    manual_selic_by_year: sortedMap(s.manual_selic_by_year),
    manual_ipca_by_year: sortedMap(s.manual_ipca_by_year),
  });

export const isDirty = (built: Settings, orig: Settings): boolean => canon(built) !== canon(orig);

/** Nome amigável de um caminho de erro do backend ("ir_brackets.1.max_days"). */
export function fieldLabel(path: string): string {
  const [head, idx, sub] = path.split(".");
  const n = Number(idx) + 1;
  switch (head) {
    case "ir_brackets": return sub === "rate" ? `Alíquota da faixa ${n} de IR` : `Faixa ${n} de IR`;
    case "iof_table": return Number.isNaN(n) ? "Tabela de IOF" : `IOF no dia ${n}`;
    case "ir_exempt_types": return "Isentos de IR";
    case "iof_exempt_types": return "Isentos de IOF";
    case "come_cotas_longo": return "Come-cotas (longo prazo)";
    case "come_cotas_curto": return "Come-cotas (curto prazo)";
    case "ir_fundo_curto_ate_180": return "IR de fundo de curto prazo (até 180 dias)";
    case "ir_fundo_curto_acima_180": return "IR de fundo de curto prazo (acima de 180 dias)";
    case "custodia_b3_aa": return "Custódia B3";
    case "tesouro_selic_isencao_custodia": return "Isenção de custódia do Tesouro Selic";
    case "spread_cdi_selic": return "Spread do CDI sobre a Selic";
    case "projection_mode": return "Fonte das projeções";
    case "manual_selic_by_year": return idx ? `Selic manual de ${idx}` : "Selic manual";
    case "manual_ipca_by_year": return idx ? `IPCA manual de ${idx}` : "IPCA manual";
    case "market_cache_ttl_hours": return "Validade dos dados em cache";
    case "fgc_limite": return "Limite do FGC";
    case "prazo_min_meses_lci": return "Prazo mínimo da LCI";
    case "prazo_min_meses_lci_ipca": return "Prazo mínimo da LCI IPCA+";
    case "prazo_min_meses_lca": return "Prazo mínimo da LCA";
    case "prazo_min_meses_lca_ipca": return "Prazo mínimo da LCA IPCA+";
    case "prazo_min_meses_lcd": return "Prazo mínimo da LCD";
    case "oferta_alerta_dias": return "Alertar após (dias)";
    case "oferta_expira_dias": return "Tirar do ranking após (dias)";
    default: return path;
  }
}

export type GrupoId = "tributacao" | "custos" | "projecoes" | "dados" | "alertas" | "prazos" | "ofertas";

export function fieldGroup(path: string): GrupoId | null {
  const head = path.split(".")[0];
  if (["ir_brackets", "iof_table", "ir_exempt_types", "iof_exempt_types", "come_cotas_longo", "come_cotas_curto", "ir_fundo_curto_ate_180", "ir_fundo_curto_acima_180"].includes(head)) return "tributacao";
  if (["custodia_b3_aa", "tesouro_selic_isencao_custodia"].includes(head)) return "custos";
  if (["projection_mode", "manual_selic_by_year", "manual_ipca_by_year", "spread_cdi_selic"].includes(head)) return "projecoes";
  if (head === "market_cache_ttl_hours") return "dados";
  if (head === "fgc_limite") return "alertas";
  if (head.startsWith("prazo_min_meses_")) return "prazos";
  if (head === "oferta_alerta_dias" || head === "oferta_expira_dias") return "ofertas";
  return null;
}

/** "campo.sub: mensagem" → { path, message }; mensagens sem campo ficam com path vazio. */
export function parseServerError(raw: string): { path: string; message: string } {
  const m = /^([a-z_]+(?:\.[\w]+)*): (.*)$/s.exec(raw);
  return m ? { path: m[1], message: m[2] } : { path: "", message: raw };
}
