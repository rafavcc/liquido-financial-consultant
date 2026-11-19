import type { MarketSummary, SimulationResponse, SimulationResult } from "../api/types";

export const fixtureResult: SimulationResult = {
  product: {
    id: "exemplo-01", tipo: "CDB", nome: "CDB Banco Alfa", emissor: "Banco Alfa", plataforma: "XP",
    indexador: "PCT_CDI", taxa: "1.12", data_vencimento: "2028-11-15", valor_minimo: "1000",
    liquidez: "NO_VENCIMENTO", data_carencia: null, cobertura: "FGC", ativo: true, exemplo: false,
    observacoes: "", taxa_adm: null, prazo_resgate_dias: null, classe_tributaria: null,
  },
  secao: "VENCE_ATE_DATA", resgatavel: true, estimativa_mercado: false, data_saida: "2028-11-16",
  dias_parado: 0, valor_investido: "50000", sobra: "0", valor_bruto: "74000.5", iof: "0.00", ir: "3000",
  custodia: "0", come_cotas: "0", taxa_adm: "0", valor_liquido: "71840.1", rentab_liquida: "0.4368",
  taxa_liquida_aa: "0.1180", data_solicitacao_resgate: null,
  alertas: [{ code: "PROJECAO", message: "Depende de projeção de CDI (Focus 13/11/2026)" }],
  serie: [],
};

export const fixtureResponse: SimulationResponse = {
  vence_ate_data: [fixtureResult],
  vence_depois: [],
  indisponiveis: [],
  mercado: {
    selic_meta: "0.1375", selic_meta_data: "2026-11-05", cdi_aa: "0.1365", ipca_12m: "0.0463", ipca_12m_ref: "2026-10-01",
    fonte_projecao: null, projecao: [], fetched_at: {}, errors: {}, tesouro_data_base: null,
  },
};

/** CDB curto, sem IOF e com IR de R$ 264,42, com série para o gráfico. */
export const fixtureDetail: SimulationResult = {
  ...fixtureResult,
  data_saida: "2027-11-17",
  dias_parado: 2,
  data_solicitacao_resgate: "2027-11-15",
  valor_investido: "10000",
  sobra: "0",
  valor_bruto: "11762.80",
  iof: "0.00",
  ir: "264.42",
  valor_liquido: "11498.38",
  rentab_liquida: "0.1498",
  taxa_liquida_aa: "0.1498",
  serie: [
    { data: "2026-11-19", valor_bruto: "10000" },
    { data: "2027-05-19", valor_bruto: "10850.40" },
    { data: "2027-11-17", valor_bruto: "11762.80" },
  ],
};

export const fixtureMercadoProjecao: MarketSummary = {
  ...fixtureResponse.mercado,
  fonte_projecao: "Focus 13/11/2026",
  projecao: [
    { ano: 2027, selic: "0.1275", ipca: "0.0490" },
    { ano: 2028, selic: "0.1100", ipca: "0.0400" },
  ],
};
