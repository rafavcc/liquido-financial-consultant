import { Area, AreaChart, CartesianGrid, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import type { SeriePoint } from "../api/types";
import { formatBRL, formatDate } from "../lib/format";

// Cores via variáveis CSS (canais RGB) para acompanhar o tema claro/escuro.
const ACCENT = "rgb(var(--accent))";
const LINE = "rgb(var(--line))";
const MUTED = "rgb(var(--muted))";

const monthYear = (iso: string) => `${iso.slice(5, 7)}/${iso.slice(0, 4)}`;
const compact = (n: number) =>
  new Intl.NumberFormat("pt-BR", { notation: "compact", maximumFractionDigits: 1 }).format(n);

interface Props {
  serie: SeriePoint[];
}

/** Evolução do valor bruto ao longo do tempo. Sem pelo menos dois pontos não há o que desenhar. */
export function EvolutionChart({ serie }: Props) {
  if (serie.length < 2) return null;
  const data = serie.map((p) => ({ data: p.data, valor: Number(p.valor_bruto) }));
  const min = Math.min(...data.map((d) => d.valor));
  const max = Math.max(...data.map((d) => d.valor));
  const pad = (max - min) * 0.08 || max * 0.02;

  return (
    <div
      role="img"
      aria-label={`Evolução do valor bruto de ${formatBRL(serie[0].valor_bruto)} a ${formatBRL(serie[serie.length - 1].valor_bruto)}`}
      className="h-52 w-full"
    >
      <ResponsiveContainer width="100%" height="100%">
        <AreaChart data={data} margin={{ top: 8, right: 8, bottom: 0, left: 0 }}>
          <defs>
            <linearGradient id="evolucao-fill" x1="0" y1="0" x2="0" y2="1">
              <stop offset="0%" stopColor={ACCENT} stopOpacity={0.32} />
              <stop offset="100%" stopColor={ACCENT} stopOpacity={0.02} />
            </linearGradient>
          </defs>
          <CartesianGrid stroke={LINE} strokeDasharray="3 3" vertical={false} />
          <XAxis
            dataKey="data"
            tickFormatter={monthYear}
            tick={{ fill: MUTED, fontSize: 11 }}
            tickLine={false}
            axisLine={{ stroke: LINE }}
            minTickGap={36}
          />
          <YAxis
            domain={[min - pad, max + pad]}
            tickFormatter={compact}
            tick={{ fill: MUTED, fontSize: 11 }}
            tickLine={false}
            axisLine={false}
            width={52}
          />
          <Tooltip
            formatter={(v: number) => [formatBRL(String(v)), "Valor bruto"]}
            labelFormatter={(l: string) => formatDate(l)}
            cursor={{ stroke: MUTED, strokeDasharray: "3 3" }}
            contentStyle={{
              background: "rgb(var(--surface))",
              border: `1px solid ${LINE}`,
              borderRadius: 12,
              fontSize: 12,
              color: "rgb(var(--ink))",
            }}
            labelStyle={{ color: MUTED }}
            itemStyle={{ color: "rgb(var(--ink))" }}
          />
          <Area
            type="monotone"
            dataKey="valor"
            stroke={ACCENT}
            strokeWidth={2}
            fill="url(#evolucao-fill)"
            dot={false}
            activeDot={{ r: 4, fill: ACCENT, stroke: "rgb(var(--surface))" }}
            isAnimationActive={false}
          />
        </AreaChart>
      </ResponsiveContainer>
    </div>
  );
}
