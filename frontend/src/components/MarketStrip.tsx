import type { MarketSummary } from "../api/types";
import { formatDateTime, formatPct } from "../lib/format";
import { IconRefresh } from "./Icons";

const FONTES: Record<string, string> = {
  bcb: "Banco Central (Selic, CDI, IPCA)",
  focus: "Boletim Focus (projeções)",
  tesouro: "Tesouro Direto (preços)",
};

interface Props {
  mercado: MarketSummary | undefined;
  refreshing: boolean;
  onRefresh: () => void;
}

const Stat = ({ label, value }: { label: string; value: string }) => (
  <div className="min-w-0">
    <div className="text-[11px] font-medium uppercase tracking-wide text-muted">{label}</div>
    <div className="text-base font-semibold">{value}</div>
  </div>
);

export function MarketStrip({ mercado, refreshing, onRefresh }: Props) {
  const errors = Object.entries(mercado?.errors ?? {});
  const stamps = Object.values(mercado?.fetched_at ?? {}).sort();
  const atualizado = stamps.length ? formatDateTime(stamps[stamps.length - 1]) : null;

  return (
    <section aria-label="Mercado" className="space-y-2">
      <div className="flex items-center gap-4 rounded-2xl border border-line bg-surface px-4 py-3 shadow-card">
        <div className="grid flex-1 grid-cols-3 gap-3">
          <Stat label="Selic" value={formatPct(mercado?.selic_meta)} />
          <Stat label="CDI" value={formatPct(mercado?.cdi_aa)} />
          <Stat label="IPCA 12m" value={formatPct(mercado?.ipca_12m)} />
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
      {errors.map(([source, msg]) => (
        <div key={source} role="alert" className="rounded-xl border border-warn/30 bg-warn-bg px-3 py-2 text-xs text-warn">
          <strong className="font-semibold">Falha ao atualizar {FONTES[source] ?? source}.</strong>{" "}
          <span className="opacity-90">{msg}</span>
        </div>
      ))}
    </section>
  );
}
