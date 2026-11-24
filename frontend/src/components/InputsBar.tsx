import type { Horizonte } from "../api/types";
import { formatDate, maskBRL } from "../lib/format";
import { HORIZONTES } from "../lib/labels";

interface Props {
  valor: string;
  dataAlvo: string;
  minDate: string;
  onValor: (v: string) => void;
  onData: (d: string) => void;
  horizonte: Horizonte;
  onHorizonte: (h: Horizonte) => void;
  dataResolvida: string | null;
}

const label = "mb-1 block text-xs font-medium text-muted";
const field =
  "w-full rounded-xl border border-line bg-surface px-3 py-2.5 text-base font-semibold shadow-card transition placeholder:font-normal placeholder:text-muted focus:border-accent focus:outline-none focus:ring-2 focus:ring-accent/30";

export function InputsBar({ valor, dataAlvo, minDate, onValor, onData, horizonte, onHorizonte, dataResolvida }: Props) {
  return (
    <section aria-label="Simulação" className="grid grid-cols-1 gap-3 sm:grid-cols-2">
      <div>
        <label htmlFor="valor" className={label}>Quanto você quer investir?</label>
        <div className="relative">
          <span className="pointer-events-none absolute left-3 top-1/2 -translate-y-1/2 text-base font-semibold text-muted">R$</span>
          <input
            id="valor"
            inputMode="decimal"
            autoComplete="off"
            placeholder="50.000,00"
            value={valor}
            onChange={(e) => onValor(maskBRL(e.target.value))}
            className={`${field} pl-10`}
          />
        </div>
      </div>
      <div>
        <span className={label}>Horizonte</span>
        <div role="radiogroup" aria-label="Horizonte" className="mb-2 flex flex-wrap gap-1.5">
          {HORIZONTES.map((h) => {
            const on = h.id === horizonte;
            return (
              <button
                key={h.id}
                type="button"
                role="radio"
                aria-checked={on}
                onClick={() => onHorizonte(h.id)}
                className={`rounded-full border px-3 py-1 text-xs font-medium transition ${
                  on ? "border-accent bg-accent text-accent-fg" : "border-line bg-surface text-muted hover:text-ink"
                }`}
              >
                {h.label}
              </button>
            );
          })}
        </div>
        {horizonte === "DATA" && (
          <>
            <label htmlFor="data-alvo" className={label}>Preciso do dinheiro em</label>
            <input
              id="data-alvo"
              type="date"
              min={minDate}
              value={dataAlvo}
              onChange={(e) => onData(e.target.value)}
              className={field}
            />
          </>
        )}
        {(horizonte === "UM_ANO" || horizonte === "DOIS_ANOS") && dataResolvida && (
          <p className="text-sm text-muted">Resgate em {formatDate(dataResolvida)}</p>
        )}
        {horizonte === "SEM_DATA" && (
          <p className="text-sm text-muted">Cada produto até o vencimento (ou 1 ano, se tiver liquidez diária)</p>
        )}
      </div>
    </section>
  );
}
