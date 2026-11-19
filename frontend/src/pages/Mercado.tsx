import { useQuery } from "@tanstack/react-query";
import { CartesianGrid, Legend, Line, LineChart, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import { api, ApiError } from "../api/client";
import type { ProjecaoAno } from "../api/types";
import { formatDate, formatPct } from "../lib/format";

// Cores via variáveis CSS (canais RGB) para acompanhar o tema claro/escuro.
const SELIC = "rgb(var(--accent))";
const IPCA = "rgb(var(--warn))";
const LINE = "rgb(var(--line))";
const MUTED = "rgb(var(--muted))";

const FONTES: Record<string, string> = { bcb: "Banco Central", focus: "Boletim Focus", tesouro: "Tesouro Direto" };
const refMonth = (iso: string) => `${iso.slice(5, 7)}/${iso.slice(0, 4)}`;
const pctAxis = (n: number) => `${new Intl.NumberFormat("pt-BR", { maximumFractionDigits: 1 }).format(n)}%`;

function Indicator({ label, value, note }: { label: string; value: string; note: string }) {
  return (
    <div className="rounded-2xl border border-line bg-surface px-4 py-3 shadow-card sm:p-4">
      <div className="text-[11px] font-medium uppercase tracking-wide text-muted">{label}</div>
      <div className="num mt-1 text-2xl font-semibold tracking-tight">{value}</div>
      <div className="mt-0.5 text-xs text-muted">{note}</div>
    </div>
  );
}

function ProjectionChart({ rows }: { rows: ProjecaoAno[] }) {
  if (rows.length < 2) return null;
  const data = rows.map((r) => ({ ano: String(r.ano), selic: Number(r.selic) * 100, ipca: Number(r.ipca) * 100 }));
  const fmt = (v: unknown) => (typeof v === "number" ? `${new Intl.NumberFormat("pt-BR", { minimumFractionDigits: 2, maximumFractionDigits: 2 }).format(v)}%` : String(v));
  return (
    <div role="img" aria-label="Gráfico de linhas da Selic no fim do ano e do IPCA projetado por ano" className="h-64 w-full">
      <ResponsiveContainer width="100%" height="100%">
        <LineChart data={data} margin={{ top: 8, right: 12, bottom: 0, left: 0 }}>
          <CartesianGrid stroke={LINE} strokeDasharray="3 3" vertical={false} />
          <XAxis dataKey="ano" tick={{ fill: MUTED, fontSize: 11 }} tickLine={false} axisLine={{ stroke: LINE }} />
          <YAxis tickFormatter={pctAxis} tick={{ fill: MUTED, fontSize: 11 }} tickLine={false} axisLine={false} width={44} domain={[0, "auto"]} />
          <Tooltip
            formatter={(v) => fmt(v)}
            labelFormatter={(l) => `Ano ${l}`}
            contentStyle={{ background: "rgb(var(--surface))", border: `1px solid ${LINE}`, borderRadius: 12, fontSize: 12, color: "rgb(var(--ink))" }}
          />
          <Legend iconType="plainline" wrapperStyle={{ fontSize: 12, color: MUTED }} />
          <Line name="Selic no fim do ano" type="monotone" dataKey="selic" stroke={SELIC} strokeWidth={2.5} dot={{ r: 3, fill: SELIC }} isAnimationActive={false} />
          <Line name="IPCA projetado" type="monotone" dataKey="ipca" stroke={IPCA} strokeWidth={2.5} strokeDasharray="6 4" dot={{ r: 3, fill: IPCA }} isAnimationActive={false} />
        </LineChart>
      </ResponsiveContainer>
    </div>
  );
}

export function Mercado() {
  const q = useQuery({ queryKey: ["market"], queryFn: api.market, retry: false });
  const m = q.data;

  if (q.isPending) return <p className="py-16 text-center text-sm text-muted">Carregando dados de mercado…</p>;
  if (!m) {
    return (
      <div role="alert" className="rounded-xl border border-neg/30 bg-neg-bg px-3 py-2 text-sm text-neg">
        {q.error instanceof ApiError ? q.error.messages.join(" ") : "Não foi possível carregar os dados de mercado."}
      </div>
    );
  }

  return (
    <div className="space-y-5">
      <div>
        <h1 className="text-xl font-semibold tracking-tight">Mercado</h1>
        <p className="mt-0.5 text-sm text-muted">Taxas de hoje e projeções usadas nos cálculos. Para atualizar os dados, vá em Configurações.</p>
      </div>

      {Object.entries(m.errors).map(([source, msg]) => (
        <div key={source} role="alert" className="rounded-xl border border-warn/30 bg-warn-bg px-3 py-2 text-xs text-warn">
          <strong className="font-semibold">Falha ao atualizar {FONTES[source] ?? source}.</strong> <span className="opacity-90">{msg}</span>
        </div>
      ))}

      <section aria-label="Indicadores" className="grid gap-3 sm:grid-cols-3">
        <Indicator label="Selic meta" value={formatPct(m.selic_meta)} note="Taxa básica de juros, ao ano" />
        <Indicator label="CDI" value={formatPct(m.cdi_aa)} note="Referência dos CDBs, ao ano" />
        <Indicator label="IPCA 12 meses" value={formatPct(m.ipca_12m)} note={m.ipca_12m_ref ? `Inflação acumulada, ref. ${refMonth(m.ipca_12m_ref)}` : "Inflação acumulada"} />
      </section>

      <section aria-labelledby="m-proj" className="rounded-2xl border border-line bg-surface p-4 shadow-card sm:p-5">
        <h2 id="m-proj" className="text-base font-semibold">Projeção por ano</h2>
        <p className="mt-0.5 text-sm text-muted">
          {m.fonte_projecao ? `Fonte: ${m.fonte_projecao}.` : "Fonte da projeção indisponível."}
        </p>
        {m.projecao.length === 0 ? (
          <p className="mt-4 rounded-xl border border-dashed border-line px-4 py-6 text-center text-sm text-muted">
            Sem projeções disponíveis no momento. Atualize os dados em Configurações ou informe valores manualmente.
          </p>
        ) : (
          <>
            <div className="mt-4 overflow-hidden rounded-xl border border-line">
              <table className="w-full text-sm">
                <thead className="bg-subtle text-left text-xs text-muted">
                  <tr>
                    <th scope="col" className="px-3 py-2 font-medium">Ano</th>
                    <th scope="col" className="px-3 py-2 text-right font-medium">Selic no fim do ano</th>
                    <th scope="col" className="px-3 py-2 text-right font-medium">IPCA projetado</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-line">
                  {m.projecao.map((r) => (
                    <tr key={r.ano}>
                      <td className="px-3 py-2 font-medium">{r.ano}</td>
                      <td className="num px-3 py-2 text-right">{formatPct(r.selic)}</td>
                      <td className="num px-3 py-2 text-right">{formatPct(r.ipca)}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
            <p className="mt-2 text-xs text-muted">Ano corrente inclui meses já divulgados estimados pela projeção.</p>
            <div className="mt-4">
              <ProjectionChart rows={m.projecao} />
            </div>
          </>
        )}
      </section>

      <p className="px-1 text-xs text-muted">
        Tesouro Direto: preços e taxas {m.tesouro_data_base ? `de ${formatDate(m.tesouro_data_base)}` : "ainda não carregados"}.
      </p>
    </div>
  );
}
