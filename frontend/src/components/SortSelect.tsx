import { ORDENACOES } from "../lib/labels";
import type { Ordenacao } from "../lib/ordering";

interface Props {
  value: Ordenacao;
  onChange: (o: Ordenacao) => void;
  /** Sem data não há valor líquido comparável entre prazos diferentes. */
  semData: boolean;
}

export function SortSelect({ value, onChange, semData }: Props) {
  return (
    <select
      aria-label="Ordenar por"
      value={value}
      onChange={(e) => onChange(e.target.value as Ordenacao)}
      className="rounded-full border border-line bg-surface px-3 py-1 text-xs font-medium text-muted focus:border-accent focus:outline-none"
    >
      {ORDENACOES.filter((o) => !(semData && o.id === "VALOR_LIQUIDO")).map((o) => (
        <option key={o.id} value={o.id}>{o.label}</option>
      ))}
    </select>
  );
}
