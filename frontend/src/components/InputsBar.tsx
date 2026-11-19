import { maskBRL } from "../lib/format";

interface Props {
  valor: string;
  dataAlvo: string;
  minDate: string;
  onValor: (v: string) => void;
  onData: (d: string) => void;
}

const label = "mb-1 block text-xs font-medium text-muted";
const field =
  "w-full rounded-xl border border-line bg-surface px-3 py-2.5 text-base font-semibold shadow-card transition placeholder:font-normal placeholder:text-muted focus:border-accent focus:outline-none focus:ring-2 focus:ring-accent/30";

export function InputsBar({ valor, dataAlvo, minDate, onValor, onData }: Props) {
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
        <label htmlFor="data-alvo" className={label}>Preciso do dinheiro em</label>
        <input
          id="data-alvo"
          type="date"
          min={minDate}
          value={dataAlvo}
          onChange={(e) => onData(e.target.value)}
          className={field}
        />
      </div>
    </section>
  );
}
