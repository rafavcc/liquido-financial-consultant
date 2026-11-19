import type { SimulationResponse, SimulationResult } from "../api/types";

export const fixtureResult: SimulationResult = {
  product: {
    id: "exemplo-01", tipo: "CDB", nome: "CDB Banco Alfa", emissor: "Banco Alfa", plataforma: "XP",
    indexador: "PCT_CDI", taxa: "1.12", data_vencimento: "2028-11-15", valor_minimo: "1000",
    liquidez: "NO_VENCIMENTO", data_carencia: null, cobertura: "FGC", ativo: true, exemplo: false,
    observacoes: "", taxa_adm: null, prazo_resgate_dias: null, classe_tributaria: null,
  },
  secao: "VENCE_ATE_DATA", resgatavel: true, estimativa_mercado: false, data_saida: "2028-11-16",
  dias_parado: 0, valor_investido: "50000", valor_bruto: "74000.5", iof: "0.00", ir: "3000",
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
    selic_meta: "0.1375", cdi_aa: "0.1365", ipca_12m: "0.0463", ipca_12m_ref: "2026-10-01",
    fonte_projecao: null, projecao: [], fetched_at: {}, errors: {}, tesouro_data_base: null,
  },
};
