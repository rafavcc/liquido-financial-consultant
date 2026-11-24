// Espelho dos contratos JSON do backend. Decimal trafega como string; datas como YYYY-MM-DD.
export type Decimal = string;

export type ProductType =
  | "CDB" | "LCI" | "LCA" | "LCD" | "CRI" | "CRA"
  | "TESOURO_SELIC" | "TESOURO_PREFIXADO" | "TESOURO_PREFIXADO_JUROS"
  | "TESOURO_IPCA" | "TESOURO_IPCA_JUROS" | "TESOURO_RENDA_MAIS" | "TESOURO_EDUCA_MAIS"
  | "FUNDO_RF";
export type Indexer = "PRE" | "PCT_CDI" | "CDI_MAIS" | "IPCA_MAIS" | "SELIC";
export type Liquidity = "NO_VENCIMENTO" | "DIARIA" | "DIARIA_APOS_CARENCIA";
export type Coverage = "FGC" | "TESOURO" | "NENHUMA";
export type Section = "VENCE_ATE_DATA" | "VENCE_DEPOIS" | "INDISPONIVEL";
export type AlertCode =
  | "PROJECAO" | "FGC_LIMITE" | "SEM_FGC" | "ESTIMATIVA_MERCADO" | "FUNDO_SEM_GARANTIA"
  | "PARADO" | "EXEMPLO" | "MODELO_SIMPLIFICADO" | "ABAIXO_MINIMO" | "NAO_RESGATAVEL"
  | "SEM_DADOS_MERCADO" | "RESGATE_DN" | "ERRO_CALCULO" | "VENCIDO" | "OFERTA_ANTIGA" | "IMPORTADO_IA";

export interface ProductData {
  id: string;
  tipo: ProductType;
  nome: string;
  emissor: string;
  plataforma: string;
  indexador: Indexer;
  taxa: Decimal;
  data_vencimento: string | null;
  valor_minimo: Decimal;
  liquidez: Liquidity;
  data_carencia: string | null;
  cobertura: Coverage;
  ativo: boolean;
  exemplo: boolean;
  observacoes: string;
  taxa_adm: Decimal | null;
  prazo_resgate_dias: number | null;
  classe_tributaria: "LONGO" | "CURTO" | null;
  data_registro: string | null;
  disponivel_ate: string | null;
  origem: "MANUAL" | "IA";
  print_id: string | null;
  juros_periodicos: "MENSAL" | "TRIMESTRAL" | "SEMESTRAL" | "ANUAL" | null;
  amortizacao: { periodicidade: string; inicio: string | null } | null;
}

export interface ProductView extends ProductData {
  idade_dias: number | null;
  expirada: boolean;
}

export interface Alert {
  code: AlertCode;
  message: string;
}

export interface SeriePoint {
  data: string;
  valor_bruto: Decimal;
}

export interface SimulationResult {
  product: ProductData;
  secao: Section;
  resgatavel: boolean;
  estimativa_mercado: boolean;
  data_saida: string | null;
  dias_parado: number;
  valor_investido: Decimal;
  sobra: Decimal;
  valor_bruto: Decimal | null;
  iof: Decimal;
  ir: Decimal;
  custodia: Decimal;
  come_cotas: Decimal;
  taxa_adm: Decimal;
  valor_liquido: Decimal | null;
  rentab_liquida: Decimal | null;
  taxa_liquida_aa: Decimal | null;
  data_solicitacao_resgate: string | null;
  alertas: Alert[];
  serie: SeriePoint[];
}

export interface ProjecaoAno {
  ano: number;
  selic: Decimal;
  ipca: Decimal;
}

export interface MarketSummary {
  selic_meta: Decimal | null;
  selic_meta_data: string | null;
  cdi_aa: Decimal | null;
  ipca_12m: Decimal | null;
  ipca_12m_ref: string | null;
  fonte_projecao: string | null;
  projecao: ProjecaoAno[];
  fetched_at: Record<string, string>;
  errors: Record<string, string>;
  tesouro_data_base: string | null;
}

export interface SimulationResponse {
  vence_ate_data: SimulationResult[];
  vence_depois: SimulationResult[];
  indisponiveis: SimulationResult[];
  mercado: MarketSummary;
}

export interface IrBracket {
  max_days: number | null;
  rate: Decimal;
}

export interface Settings {
  ir_brackets: IrBracket[];
  iof_table: Decimal[];
  ir_exempt_types: ProductType[];
  iof_exempt_types: ProductType[];
  come_cotas_longo: Decimal;
  come_cotas_curto: Decimal;
  ir_fundo_curto_ate_180: Decimal;
  ir_fundo_curto_acima_180: Decimal;
  custodia_b3_aa: Decimal;
  tesouro_selic_isencao_custodia: Decimal;
  spread_cdi_selic: Decimal;
  projection_mode: string;
  manual_selic_by_year: Record<string, Decimal>;
  manual_ipca_by_year: Record<string, Decimal>;
  market_cache_ttl_hours: number;
  fgc_limite: Decimal;
  prazo_min_meses_lci: number;
  prazo_min_meses_lci_ipca: number;
  prazo_min_meses_lca: number;
  prazo_min_meses_lca_ipca: number;
  prazo_min_meses_lcd: number;
  oferta_alerta_dias: number;
  oferta_expira_dias: number;
}

export interface ImportStatus {
  configurado: boolean;
  alcancavel: boolean | null;
  modelo: string | null;
}

export type ImportItemStatus = "NA_FILA" | "LENDO" | "CONCLUIDO" | "ERRO";

export interface ImportItemView {
  id: string;
  nome_arquivo: string;
  print_id: string;
  status: ImportItemStatus;
  erro: string | null;
  criados: number;
  renovados: number;
  ignorados: number;
  falhas: number;
}

export interface ImportBatchView {
  id: string;
  criado_em: string;
  pendentes: number;
  itens: ImportItemView[];
}

export interface ImportCreated {
  lote: ImportBatchView;
  recusados: string[];
}

export interface ImportFailureView {
  id: string;
  item_id: string;
  print_id: string | null;
  nome_arquivo: string | null;
  erros: string[];
  parcial: { raw?: Record<string, unknown>; interpretado?: Partial<ProductData> };
  status: string;
}
