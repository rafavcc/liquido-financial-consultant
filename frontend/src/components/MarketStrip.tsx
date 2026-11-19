import type { MarketSummary } from "../api/types";
import { formatDate, formatPct } from "../lib/format";
import { FONTE_NOME, formatDayMonthTime, oldestFetchedAt, refMonth, staleMessage } from "../lib/market";
import { IconRefresh } from "./Icons";

interface Props {
  mercado: MarketSummary | undefined;
  refreshing: boolean;
  onRefresh: () => void;
}

const Stat = ({ label, value, note }: { label: string; value: string; note?: string }) => (
  <div className="min-w-0">
    <div className="text-[11px] font-medium uppercase tracking-wide text-muted">{label}</div>
    <div className="text-base font-semibold">{value}</div>
    {note && <div className="text-[10px] text-muted">{note}</div>}
  </div>
);

export function MarketStrip({ mercado, refreshing, onRefresh }: Props) {
  const errors = Object.entries(mercado?.errors ?? {});
  const stamps = Object.entries(mercado?.fetched_at ?? {});
  const oldest = oldestFetchedAt(mercado?.fetched_at ?? {});
  const atualizado = oldest ? formatDayMonthTime(oldest) : null;
  const selicNote = mercado?.selic_meta_data ? `em ${formatDate(mercado.selic_meta_data)}` : undefined;

  return (
    <section aria-label="Mercado" className="space-y-2">
      <div className="flex items-center gap-4 rounded-2xl border border-line bg-surface px-4 py-3 shadow-card">
        <div className="grid flex-1 grid-cols-3 gap-3">
          <Stat label="Selic" value={formatPct(mercado?.selic_meta)} note={selicNote} />
          <Stat label="CDI" value={formatPct(mercado?.cdi_aa)} note={selicNote} />
          <Stat
            label="IPCA 12m"
            value={formatPct(mercado?.ipca_12m)}
            note={mercado?.ipca_12m_ref ? `ref. ${refMonth(mercado.ipca_12m_ref)}` : undefined}
          />
        </div>
        <div className="flex shrink-0 flex-col items-end gap-1 text-right">
          <button
            type="button"
            onClick={onRefresh}
            disabled={refreshing}
            aria-label="Atualizar dados de mercado"
            title="Atualizar dados de mercado"
            className="flex h-8 w-8 items-center justify-center rounded-full border border-line text-muted transition hover:text-accent disabled:opacity-60 [&_svg]:h-4 [&_svg]:w-4"
          >
            <IconRefresh spin={refreshing} />
          </button>
          {atualizado && <span className="hidden text-[11px] text-muted sm:block">Atualizado em {atualizado}</span>}
        </div>
      </div>
      {atualizado && <p className="px-1 text-[11px] text-muted sm:hidden">Atualizado em {atualizado}</p>}
      {stamps.length > 0 && (
        <details className="px-1 text-[11px] text-muted">
          <summary className="cursor-pointer select-none">Dados por fonte</summary>
          <ul className="mt-1 space-y-0.5">
            {stamps.map(([source, at]) => (
              <li key={source}>
                {FONTE_NOME[source] ?? source}: {formatDayMonthTime(at)}
              </li>
            ))}
            {mercado?.tesouro_data_base && <li>Preços do Tesouro de {formatDate(mercado.tesouro_data_base)}</li>}
          </ul>
        </details>
      )}
      {errors.map(([source, msg]) => (
        <div key={source} role="alert" className="rounded-xl border border-warn/30 bg-warn-bg px-3 py-2 text-xs text-warn">
          {staleMessage(source, msg, mercado?.fetched_at[source])}
        </div>
      ))}
    </section>
  );
}
