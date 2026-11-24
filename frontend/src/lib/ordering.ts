import type { Coverage, SimulationResult } from "../api/types";

export type Ordenacao = "VALOR_LIQUIDO" | "TAXA" | "CUSTO_BENEFICIO" | "PRAZO" | "SEGURANCA";

const num = (v: string | null): number => Number(v);

/** Resultado comparável na dominância: resgatável e com taxa e prazo conhecidos. */
const comparavel = (r: SimulationResult): boolean =>
  r.resgatavel && r.taxa_liquida_aa !== null && r.prazo_saida_dias !== null;

/** A domina B: taxa >= e prazo <= com ao menos uma desigualdade estrita. */
function domina(a: SimulationResult, b: SimulationResult): boolean {
  const ta = num(a.taxa_liquida_aa), tb = num(b.taxa_liquida_aa);
  const pa = a.prazo_saida_dias as number, pb = b.prazo_saida_dias as number;
  return ta >= tb && pa <= pb && (ta > tb || pa < pb);
}

/** Ids dominados dentro da lista recebida (que deve ser a lista visível, já filtrada). */
export function dominados(list: SimulationResult[]): Set<string> {
  const cands = list.filter(comparavel);
  const out = new Set<string>();
  for (const b of cands) {
    if (cands.some((a) => a !== b && domina(a, b))) out.add(b.product.id);
  }
  return out;
}

const COBERTURA_RANK: Record<Coverage, number> = { TESOURO: 0, FGC: 1, NENHUMA: 2 };

/** Menor primeiro; nulo vai para o fim. */
type Cmp = (a: SimulationResult, b: SimulationResult) => number;

const nullsLast = (get: (r: SimulationResult) => number | null, desc: boolean): Cmp => (a, b) => {
  const x = get(a), y = get(b);
  if (x === null && y === null) return 0;
  if (x === null) return 1;
  if (y === null) return -1;
  return desc ? y - x : x - y;
};

const taxaDesc = nullsLast((r) => (r.taxa_liquida_aa === null ? null : num(r.taxa_liquida_aa)), true);
const prazoAsc = nullsLast((r) => r.prazo_saida_dias, false);
const valorDesc = nullsLast((r) => (r.valor_liquido === null ? null : num(r.valor_liquido)), true);
const porNome: Cmp = (a, b) => a.product.nome.localeCompare(b.product.nome, "pt-BR");

const chain = (...cmps: Cmp[]): Cmp => (a, b) => {
  for (const c of cmps) {
    const v = c(a, b);
    if (v !== 0) return v;
  }
  return 0;
};

/** Nova lista ordenada; não resgatáveis ficam no fim, na ordem original. */
export function ordenar(list: SimulationResult[], ord: Ordenacao): SimulationResult[] {
  const resgataveis = list.filter((r) => r.resgatavel);
  const presos = list.filter((r) => !r.resgatavel);
  let cmp: Cmp;
  switch (ord) {
    case "VALOR_LIQUIDO": cmp = chain(valorDesc, taxaDesc, porNome); break;
    case "TAXA": cmp = chain(taxaDesc, porNome); break;
    case "PRAZO": cmp = chain(prazoAsc, taxaDesc, porNome); break;
    case "SEGURANCA":
      cmp = chain((a, b) => COBERTURA_RANK[a.product.cobertura] - COBERTURA_RANK[b.product.cobertura], taxaDesc, porNome);
      break;
    case "CUSTO_BENEFICIO": {
      const dom = dominados(resgataveis);
      const grupo = (r: SimulationResult) => (dom.has(r.product.id) ? 1 : 0);
      cmp = chain(
        (a, b) => grupo(a) - grupo(b),
        (a, b) => (grupo(a) === 0 ? chain(prazoAsc, taxaDesc)(a, b) : taxaDesc(a, b)),
        porNome,
      );
      break;
    }
  }
  return [...resgataveis].sort(cmp).concat(presos);
}
