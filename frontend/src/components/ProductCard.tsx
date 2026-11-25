import type { SimulationResult } from "../api/types";
import { formatBRL, formatDate, formatPct, formatPctSigned, isNegativePct } from "../lib/format";
import { indexLabel, isIsento, prazoSaidaLabel, tipoLabel } from "../lib/labels";
import type { ProductType } from "../api/types";
import { AlertBadge } from "./AlertBadge";

interface Props {
  result: SimulationResult;
  rank?: number;
  onSelect?: (result: SimulationResult) => void;
  /** Tipos isentos de IR (vem de /settings); sem ele usa a lista padrão. */
  isentoTypes?: ProductType[];
  destaque?: "valor" | "taxa";
  dominado?: boolean;
  /** Data de hoje (ISO); padrão: hoje local. */
  hoje?: string;
}

const hojeIso = () => {
  const d = new Date();
  const p = (n: number) => String(n).padStart(2, "0");
  return `${d.getFullYear()}-${p(d.getMonth() + 1)}-${p(d.getDate())}`;
};

const Chip = ({ children, className = "", title }: { children: React.ReactNode; className?: string; title?: string }) => (
  <span title={title} className={`inline-flex items-center rounded-md px-1.5 py-0.5 text-[11px] font-medium leading-4 ${className}`}>
    {children}
  </span>
);

export function ProductCard({ result, rank, onSelect, isentoTypes, destaque = "valor", dominado = false, hoje }: Props) {
  const p = result.product;
  const late = result.secao === "VENCE_DEPOIS";
  const off = result.secao === "INDISPONIVEL";
  const prazo = prazoSaidaLabel(result, hoje ?? hojeIso());
  const porTaxa = destaque === "taxa" && result.taxa_liquida_aa !== null;

  const border = late ? "border-neg/40 hover:border-neg" : off ? "border-line" : "border-line hover:border-accent";
  const stripe = late ? "before:bg-neg" : off ? "before:bg-off/40" : "before:bg-pos";

  return (
    <article
      className={`relative block w-full overflow-hidden rounded-2xl border bg-surface p-4 text-left shadow-card transition
        before:absolute before:inset-y-0 before:left-0 before:w-1 before:content-[''] ${stripe} ${border}
        ${off ? "opacity-80" : ""} hover:shadow-md focus-within:ring-2 focus-within:ring-accent`}
    >
      <div className="flex items-start justify-between gap-3">
        <div className="flex min-w-0 items-start gap-3">
          {rank !== undefined && (
            <span className="mt-0.5 flex h-7 min-w-7 shrink-0 items-center justify-center rounded-full bg-pos-bg px-1.5 text-xs font-bold text-pos">
              #{rank}
            </span>
          )}
          <div className="min-w-0">
            <h3 className="truncate text-[15px] font-semibold leading-tight">
              <button
                type="button"
                onClick={() => onSelect?.(result)}
                className="text-left after:absolute after:inset-0 after:content-[''] focus-visible:outline-none"
              >
                {p.nome}
              </button>
            </h3>
            <p className="mt-0.5 text-xs text-muted">
              {p.plataforma} · {tipoLabel(p.tipo)}
            </p>
          </div>
        </div>
        <div className="shrink-0 text-right">
          <div className={`text-xl font-bold leading-tight tracking-tight ${off ? "text-muted" : ""}`}>
            {porTaxa ? `${formatPct(result.taxa_liquida_aa as string)} a.a.` : formatBRL(result.valor_liquido)}
          </div>
          {porTaxa && (
            <div className="mt-0.5 text-xs text-muted">
              {formatBRL(result.valor_liquido)}
              {result.data_saida && ` em ${formatDate(result.data_saida)}`}
            </div>
          )}
          {result.rentab_liquida !== null && (
            <div
              className={`mt-0.5 text-xs font-semibold ${isNegativePct(result.rentab_liquida) ? "text-neg" : "text-pos"}`}
            >
              {formatPctSigned(result.rentab_liquida)}
            </div>
          )}
        </div>
      </div>

      <div className="mt-3 flex flex-wrap items-center gap-x-3 gap-y-1.5 text-xs">
        <Chip className="bg-subtle text-ink">{indexLabel(p.indexador, p.taxa)}</Chip>
        {prazo && <span className="text-muted">{prazo}</span>}
        {dominado && <Chip className="bg-warn-bg text-warn">Há opção melhor e mais curta</Chip>}
        {/* "Preso até"/"Venda antes de" já trazem a data do vencimento: não repetir. */}
        {p.data_vencimento && !prazo?.includes(formatDate(p.data_vencimento)) && (
          <span className="text-muted">Vence {formatDate(p.data_vencimento)}</span>
        )}
        {isIsento(p.tipo, isentoTypes) && <Chip className="bg-pos-bg text-pos">Isento de IR</Chip>}
        {p.cobertura === "FGC" && (
          <Chip className="bg-pos-bg text-pos" title="Coberto pelo FGC">FGC</Chip>
        )}
        {p.cobertura === "TESOURO" && (
          <Chip className="bg-pos-bg text-pos" title="Garantido pelo Tesouro Nacional">Tesouro</Chip>
        )}
        {p.cobertura === "NENHUMA" && (
          <Chip className="bg-neg-bg text-neg" title="Sem cobertura do FGC">FGC</Chip>
        )}
        {!porTaxa && result.taxa_liquida_aa !== null && (
          <span className="ml-auto font-medium text-muted">≈ {formatPct(result.taxa_liquida_aa)} a.a. líquido</span>
        )}
      </div>

      {result.alertas.length > 0 && (
        <div className="mt-3 flex flex-wrap gap-1.5">
          {result.alertas.map((a) => (
            <AlertBadge key={a.code} alert={a} />
          ))}
        </div>
      )}
    </article>
  );
}
