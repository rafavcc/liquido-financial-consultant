import type { AlertCode, Indexer, ProductData, ProductType } from "../api/types";
import { formatPct } from "./format";

export function indexLabel(indexador: Indexer, taxa: string): string {
  switch (indexador) {
    case "PCT_CDI": {
      const pct = Math.round(Number(taxa) * 10000) / 100;
      return `${formatPct(taxa, Number.isInteger(pct) ? 0 : 2)} do CDI`;
    }
    case "CDI_MAIS": return `CDI + ${formatPct(taxa)}`;
    case "IPCA_MAIS": return `IPCA + ${formatPct(taxa)}`;
    case "PRE": return `Pré ${formatPct(taxa)}`;
    case "SELIC": return `Selic + ${formatPct(taxa)}`;
  }
}

export type TipoGrupo = "CDB" | "LCI_LCA" | "CRI_CRA" | "TESOURO" | "FUNDOS";

export const TIPO_GRUPOS: { id: TipoGrupo; label: string }[] = [
  { id: "CDB", label: "CDB" },
  { id: "LCI_LCA", label: "LCI/LCA/LCD" },
  { id: "CRI_CRA", label: "CRI/CRA" },
  { id: "TESOURO", label: "Tesouro" },
  { id: "FUNDOS", label: "Fundos" },
];

export function tipoGrupo(t: ProductType): TipoGrupo {
  if (t === "CDB") return "CDB";
  if (t === "LCI" || t === "LCA" || t === "LCD") return "LCI_LCA";
  if (t === "CRI" || t === "CRA") return "CRI_CRA";
  if (t === "FUNDO_RF") return "FUNDOS";
  return "TESOURO";
}

const TIPO_LABEL: Partial<Record<ProductType, string>> = {
  TESOURO_SELIC: "Tesouro Selic",
  TESOURO_PREFIXADO: "Tesouro Prefixado",
  TESOURO_PREFIXADO_JUROS: "Tesouro Prefixado c/ juros",
  TESOURO_IPCA: "Tesouro IPCA+",
  TESOURO_IPCA_JUROS: "Tesouro IPCA+ c/ juros",
  TESOURO_RENDA_MAIS: "Tesouro Renda+",
  TESOURO_EDUCA_MAIS: "Tesouro Educa+",
  FUNDO_RF: "Fundo",
};

export const tipoLabel = (t: ProductType): string => TIPO_LABEL[t] ?? t;

/** Isenção de IR: lista vem de /settings (ir_exempt_types); esta é só o fallback enquanto carrega. */
export const ISENTOS_PADRAO: ProductType[] = ["LCI", "LCA", "LCD", "CRI", "CRA"];
export const isIsento = (t: ProductType, isentos: ProductType[] = ISENTOS_PADRAO): boolean => isentos.includes(t);

/** Prazo de resgate "D+N", só para fundos. */
export const resgateLabel = (p: ProductData): string | null =>
  p.tipo === "FUNDO_RF" && p.prazo_resgate_dias !== null ? `D+${p.prazo_resgate_dias}` : null;

export type AlertTone = "warn" | "neg" | "off" | "info";

export const ALERT_META: Record<AlertCode, { icon: string; text: string; tone: AlertTone }> = {
  PROJECAO: { icon: "📈", text: "Depende de projeção", tone: "warn" },
  ESTIMATIVA_MERCADO: { icon: "⚖️", text: "Estimativa de mercado", tone: "warn" },
  NAO_RESGATAVEL: { icon: "⛔", text: "Não resgatável na data", tone: "neg" },
  EXEMPLO: { icon: "🧪", text: "Exemplo", tone: "off" },
  FGC_LIMITE: { icon: "🛡️", text: "Acima do limite FGC", tone: "warn" },
  SEM_FGC: { icon: "🛡️", text: "Sem FGC", tone: "off" },
  FUNDO_SEM_GARANTIA: { icon: "〰️", text: "Rentabilidade não garantida", tone: "warn" },
  PARADO: { icon: "⏸️", text: "Dinheiro parado", tone: "warn" },
  MODELO_SIMPLIFICADO: { icon: "ℹ️", text: "Modelo simplificado", tone: "off" },
  ABAIXO_MINIMO: { icon: "⛔", text: "Abaixo do mínimo", tone: "neg" },
  SEM_DADOS_MERCADO: { icon: "📡", text: "Sem dados de mercado", tone: "off" },
  RESGATE_DN: { icon: "🗓️", text: "Prazo de resgate", tone: "info" },
  VENCIDO: { icon: "⌛", text: "Produto vencido", tone: "neg" },
  OFERTA_ANTIGA: { icon: "⏳", text: "Oferta antiga", tone: "warn" },
  IMPORTADO_IA: { icon: "🤖", text: "Importado por IA", tone: "off" },
  ERRO_CALCULO: { icon: "⚠️", text: "Erro de cálculo", tone: "neg" },
};
