import * as Dialog from "@radix-ui/react-dialog";
import type { MarketSummary, SimulationResult } from "../api/types";
import { formatBRL, formatDate, formatPct } from "../lib/format";
import { ALERT_META, indexLabel, isIsento, resgateLabel, tipoLabel } from "../lib/labels";
import { TONE } from "./AlertBadge";
import { EvolutionChart } from "./EvolutionChart";

interface Props {
  result: SimulationResult;
  mercado: MarketSummary;
  open: boolean;
  onOpenChange: (open: boolean) => void;
}

const isZero = (v: string) => Number(v) === 0;

function isoToday(): string {
  const d = new Date();
  const p = (n: number) => String(n).padStart(2, "0");
  return `${d.getFullYear()}-${p(d.getMonth() + 1)}-${p(d.getDate())}`;
}

const H = ({ children }: { children: React.ReactNode }) => (
  <h3 className="mb-2 text-xs font-semibold uppercase tracking-wide text-muted">{children}</h3>
);

interface Row {
  label: string;
  value: string;
  tone?: "neg" | "muted";
}

function Decomposicao({ r }: { r: SimulationResult }) {
  const bruto = Number(r.valor_bruto) - Number(r.valor_investido);
  const rows: Row[] = [
    { label: "Rendimento bruto", value: formatBRL(String(bruto)) },
    ...(!isZero(r.iof) ? [{ label: "IOF", value: formatBRL(r.iof), tone: "neg" as const }] : []),
    ...(!isZero(r.ir) ? [{ label: "IR", value: formatBRL(r.ir), tone: "neg" as const }] : []),
    ...(!isZero(r.custodia) ? [{ label: "Custódia", value: formatBRL(r.custodia), tone: "neg" as const }] : []),
    ...(!isZero(r.come_cotas) ? [{ label: "Come-cotas", value: formatBRL(r.come_cotas), tone: "neg" as const }] : []),
    ...(!isZero(r.taxa_adm)
      ? [{ label: "Taxa de adm. (já descontada)", value: formatBRL(r.taxa_adm), tone: "muted" as const }]
      : []),
  ];
  return (
    <table className="w-full text-sm">
      <tbody className="divide-y divide-line">
        <tr>
          <th scope="row" className="py-2 text-left font-normal text-muted">Valor investido</th>
          <td className="py-2 text-right font-medium">{formatBRL(r.valor_investido)}</td>
        </tr>
        {rows.map((row) => (
          <tr key={row.label}>
            <th scope="row" className="py-2 text-left font-normal text-muted">{row.label}</th>
            <td className={`py-2 text-right ${row.tone === "neg" ? "text-neg" : row.tone === "muted" ? "text-muted" : ""}`}>
              {row.tone === "neg" && <span aria-hidden="true">− </span>}
              {row.value}
            </td>
          </tr>
        ))}
        <tr>
          <th scope="row" className="pt-3 text-left text-base font-semibold">Valor líquido</th>
          <td className="pt-3 text-right text-xl font-bold tracking-tight">{formatBRL(r.valor_liquido)}</td>
        </tr>
      </tbody>
    </table>
  );
}

function Premissas({ r, mercado }: { r: SimulationResult; mercado: MarketSummary }) {
  const depende = r.alertas.some((a) => a.code === "PROJECAO");
  if (!depende) {
    return <p className="text-sm text-muted">Rentabilidade prefixada — sem dependência de projeção.</p>;
  }
  const por = (campo: "selic" | "ipca") =>
    mercado.projecao.map((p) => `${formatPct(p[campo])} em ${p.ano}`).join(", ");
  const partes = mercado.projecao.length > 0 ? [`Selic ${por("selic")}`, `IPCA ${por("ipca")}`].join(" · ") : null;
  return (
    <p className="text-sm text-muted">
      Projeção: {mercado.fonte_projecao ?? "fonte não informada"}
      {partes && ` — ${partes}`}
    </p>
  );
}

const DateRow = ({ label, value }: { label: string; value: string }) => (
  <div className="flex items-baseline justify-between gap-3 py-1.5 text-sm">
    <dt className="text-muted">{label}</dt>
    <dd className="font-medium">{value}</dd>
  </div>
);

export function ProductDetail({ result: r, mercado, open, onOpenChange }: Props) {
  const p = r.product;
  const calculado = r.valor_liquido !== null && r.valor_bruto !== null;
  const dn = resgateLabel(p);
  const solicitar =
    r.data_solicitacao_resgate && r.data_solicitacao_resgate !== r.data_saida ? r.data_solicitacao_resgate : null;
  const motivo =
    r.secao === "INDISPONIVEL"
      ? "Para este valor e data, não há valor calculado para o produto."
      : "Não há valor calculado: o produto não pode ser resgatado na data escolhida.";

  return (
    <Dialog.Root open={open} onOpenChange={onOpenChange}>
      <Dialog.Portal>
        <Dialog.Overlay className="detail-overlay fixed inset-0 z-40 bg-black/50" />
        <Dialog.Content
          className="detail-content fixed inset-0 z-50 flex flex-col overflow-hidden bg-surface text-ink shadow-xl
            sm:left-auto sm:w-[480px] sm:border-l sm:border-line"
        >
          <header className="flex items-start justify-between gap-3 border-b border-line px-5 pb-4 pt-5">
            <div className="min-w-0">
              <Dialog.Title className="text-lg font-semibold leading-tight">{p.nome}</Dialog.Title>
              <Dialog.Description className="mt-1 text-sm text-muted">
                {p.plataforma} · {tipoLabel(p.tipo)}
                {dn && ` · ${dn}`} · {indexLabel(p.indexador, p.taxa)}
                {p.data_vencimento && ` · Vence ${formatDate(p.data_vencimento)}`}
              </Dialog.Description>
              <div className="mt-2 flex flex-wrap gap-1.5 text-[11px] font-medium">
                {isIsento(p.tipo) && <span className="rounded-md bg-pos-bg px-1.5 py-0.5 text-pos">Isento de IR</span>}
                {p.cobertura === "FGC" && <span className="rounded-md bg-subtle px-1.5 py-0.5 text-muted">FGC</span>}
              </div>
            </div>
            <Dialog.Close
              aria-label="Fechar"
              className="-mr-2 -mt-1 rounded-full p-2 text-muted hover:bg-subtle hover:text-ink"
            >
              <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" aria-hidden="true">
                <path d="M6 6l12 12M18 6L6 18" />
              </svg>
            </Dialog.Close>
          </header>

          <div className="flex-1 space-y-6 overflow-y-auto px-5 py-5 pb-[max(1.25rem,env(safe-area-inset-bottom))]">
            {calculado ? (
              <>
                <section aria-label="Decomposição">
                  <H>Decomposição</H>
                  <Decomposicao r={r} />
                  <dl className="mt-3 space-y-0.5 rounded-xl bg-subtle px-3 py-2">
                    <DateRow label="Rentabilidade líquida" value={formatPct(r.rentab_liquida)} />
                    <DateRow label="≈ Taxa líquida a.a." value={formatPct(r.taxa_liquida_aa)} />
                  </dl>
                </section>

                <section aria-label="Evolução">
                  <H>Evolução do valor bruto</H>
                  <EvolutionChart serie={r.serie} />
                </section>
              </>
            ) : (
              <p className="rounded-xl border border-dashed border-line px-4 py-5 text-sm text-muted">{motivo}</p>
            )}

            {r.alertas.length > 0 && (
              <section aria-label="Alertas">
                <H>Alertas</H>
                <ul className="space-y-2">
                  {r.alertas.map((a) => {
                    const meta = ALERT_META[a.code];
                    return (
                      <li key={a.code} className={`flex items-start gap-2 rounded-xl px-3 py-2 text-sm ${TONE[meta.tone]}`}>
                        <span aria-hidden="true">{meta.icon}</span>
                        <span>{a.message}</span>
                      </li>
                    );
                  })}
                </ul>
              </section>
            )}

            <section aria-label="Datas">
              <H>Datas</H>
              <dl className="divide-y divide-line">
                <DateRow label="Aplicação" value={formatDate(isoToday())} />
                {r.data_saida && <DateRow label="Saída" value={formatDate(r.data_saida)} />}
                {solicitar && <DateRow label="Solicitar resgate até" value={formatDate(solicitar)} />}
                {r.dias_parado > 0 && <DateRow label="Dias parados" value={String(r.dias_parado)} />}
              </dl>
            </section>

            <section aria-label="Premissas">
              <H>Premissas</H>
              <Premissas r={r} mercado={mercado} />
            </section>
          </div>
        </Dialog.Content>
      </Dialog.Portal>
    </Dialog.Root>
  );
}
