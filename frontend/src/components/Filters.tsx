import type { TipoGrupo } from "../lib/labels";
import { TIPO_GRUPOS } from "../lib/labels";

export interface FilterState {
  tipos: TipoGrupo[];
  plataforma: string;
  soFgc: boolean;
  soIsentos: boolean;
}

export const EMPTY_FILTERS: FilterState = { tipos: [], plataforma: "", soFgc: false, soIsentos: false };

interface Props {
  value: FilterState;
  plataformas: string[];
  onChange: (f: FilterState) => void;
}

const pill = (on: boolean) =>
  `rounded-full border px-3 py-1 text-xs font-medium transition ${
    on ? "border-accent bg-accent text-accent-fg" : "border-line bg-surface text-muted hover:text-ink"
  }`;

export function Filters({ value, plataformas, onChange }: Props) {
  const toggleTipo = (id: TipoGrupo) =>
    onChange({
      ...value,
      tipos: value.tipos.includes(id) ? value.tipos.filter((t) => t !== id) : [...value.tipos, id],
    });
  const active =
    value.tipos.length > 0 || value.plataforma !== "" || value.soFgc || value.soIsentos;

  return (
    <section aria-label="Filtros" className="flex flex-wrap items-center gap-2">
      {TIPO_GRUPOS.map((g) => (
        <button key={g.id} type="button" aria-pressed={value.tipos.includes(g.id)} onClick={() => toggleTipo(g.id)} className={pill(value.tipos.includes(g.id))}>
          {g.label}
        </button>
      ))}
      <span className="mx-1 hidden h-4 w-px bg-line sm:block" aria-hidden="true" />
      <select
        aria-label="Plataforma"
        value={value.plataforma}
        onChange={(e) => onChange({ ...value, plataforma: e.target.value })}
        className="rounded-full border border-line bg-surface px-3 py-1 text-xs font-medium text-muted focus:border-accent focus:outline-none"
      >
        <option value="">Todas as plataformas</option>
        {plataformas.map((p) => (
          <option key={p} value={p}>{p}</option>
        ))}
      </select>
      <button type="button" aria-pressed={value.soFgc} onClick={() => onChange({ ...value, soFgc: !value.soFgc })} className={pill(value.soFgc)}>
        Só com FGC
      </button>
      <button type="button" aria-pressed={value.soIsentos} onClick={() => onChange({ ...value, soIsentos: !value.soIsentos })} className={pill(value.soIsentos)}>
        Só isentos
      </button>
      {active && (
        <button type="button" onClick={() => onChange(EMPTY_FILTERS)} className="px-1 text-xs font-medium text-accent hover:underline">
          Limpar
        </button>
      )}
    </section>
  );
}
