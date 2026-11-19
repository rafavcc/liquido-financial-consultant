import { keepPreviousData, useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useEffect, useMemo, useState } from "react";
import { api, ApiError } from "../api/client";
import type { ProductType, SimulationResult } from "../api/types";
import { EMPTY_FILTERS, Filters, type FilterState } from "../components/Filters";
import { IconChevron } from "../components/Icons";
import { InputsBar } from "../components/InputsBar";
import { MarketStrip } from "../components/MarketStrip";
import { ProductCard } from "../components/ProductCard";
import { ProductDetail } from "../components/ProductDetail";
import { SectionHeader } from "../components/SectionHeader";
import { formatDate, maskBRL } from "../lib/format";
import { ISENTOS_PADRAO, isIsento, tipoGrupo } from "../lib/labels";
import { parseBRL } from "../lib/parse";
import { readStore, writeStore } from "../lib/storage";
import { useDebounced } from "../lib/useDebounced";

const K_VALOR = "liquido.valor";
const K_DATA = "liquido.dataAlvo";

function isoDate(d: Date): string {
  const p = (n: number) => String(n).padStart(2, "0");
  return `${d.getFullYear()}-${p(d.getMonth() + 1)}-${p(d.getDate())}`;
}
function addDays(d: Date, n: number): Date {
  const c = new Date(d);
  c.setDate(c.getDate() + n);
  return c;
}

function applyFilters(list: SimulationResult[], f: FilterState, isentos: ProductType[]): SimulationResult[] {
  return list.filter((r) => {
    const p = r.product;
    if (f.tipos.length > 0 && !f.tipos.includes(tipoGrupo(p.tipo))) return false;
    if (f.plataforma && p.plataforma !== f.plataforma) return false;
    if (f.soFgc && p.cobertura !== "FGC") return false;
    if (f.soIsentos && !isIsento(p.tipo, isentos)) return false;
    return true;
  });
}

const Empty = ({ children }: { children: React.ReactNode }) => (
  <p className="rounded-2xl border border-dashed border-line px-4 py-6 text-center text-sm text-muted">{children}</p>
);

export function Comparador() {
  const qc = useQueryClient();
  const [valor, setValor] = useState(() => readStore(K_VALOR) ?? "50.000");
  const [dataAlvo, setDataAlvo] = useState(() => readStore(K_DATA) ?? isoDate(addDays(new Date(), 365 * 3)));
  const [filters, setFilters] = useState<FilterState>(EMPTY_FILTERS);
  const [showOff, setShowOff] = useState(false);
  const [selected, setSelected] = useState<SimulationResult | null>(null);

  const hoje = isoDate(new Date());
  const amanha = isoDate(addDays(new Date(), 1));
  const dValor = useDebounced(valor, 400);
  const dData = useDebounced(dataAlvo, 400);

  const valorNum = parseBRL(dValor);
  const valido = valorNum !== null && Number(valorNum) > 0 && dData > hoje;

  const sim = useQuery({
    queryKey: ["simulate", valorNum, dData],
    queryFn: () => api.simulate(valorNum as string, dData),
    enabled: valido,
    placeholderData: keepPreviousData,
    retry: false,
  });
  // /simulate já traz `mercado`; a consulta própria só serve de fallback com entradas inválidas.
  const marketQ = useQuery({ queryKey: ["market"], queryFn: api.market, retry: false, enabled: !valido });
  const settingsQ = useQuery({ queryKey: ["settings"], queryFn: api.settings.get, retry: false });
  const isentos: ProductType[] = settingsQ.data?.ir_exempt_types ?? ISENTOS_PADRAO;
  const refresh = useMutation({
    mutationFn: api.refreshMarket,
    onSuccess: (m) => {
      qc.setQueryData(["market"], m);
      void qc.invalidateQueries({ queryKey: ["simulate"] });
    },
  });

  // Com entradas inválidas (ou erro) não mostramos resultados antigos mantidos por keepPreviousData.
  const data = valido && !sim.isError ? sim.data : undefined;
  const mercado = valido ? sim.data?.mercado ?? marketQ.data : marketQ.data;
  const marketErr = refresh.error ?? (!valido ? marketQ.error : null);
  const marketMsgs = !marketErr
    ? []
    : marketErr instanceof ApiError
      ? marketErr.messages
      : ["Não foi possível atualizar os dados de mercado."];

  const plataformas = useMemo(() => {
    const all = [...(data?.vence_ate_data ?? []), ...(data?.vence_depois ?? []), ...(data?.indisponiveis ?? [])];
    return [...new Set(all.map((r) => r.product.plataforma))].sort((a, b) => a.localeCompare(b, "pt-BR"));
  }, [data]);

  // Plataforma que sumiu dos resultados não pode continuar filtrando.
  useEffect(() => {
    if (data && filters.plataforma && !plataformas.includes(filters.plataforma)) {
      setFilters((f) => ({ ...f, plataforma: "" }));
    }
  }, [data, plataformas, filters.plataforma]);

  const verdes = useMemo(() => applyFilters(data?.vence_ate_data ?? [], filters, isentos), [data, filters, isentos]);
  const vermelhos = useMemo(() => applyFilters(data?.vence_depois ?? [], filters, isentos), [data, filters, isentos]);
  const cinzas = useMemo(() => applyFilters(data?.indisponiveis ?? [], filters, isentos), [data, filters, isentos]);


  const erroValidacao =
    valorNum === null || Number(valorNum) <= 0
      ? "Informe um valor maior que zero."
      : dData <= hoje
        ? "A data deve ser posterior a hoje."
        : null;
  const erroApi = sim.error instanceof ApiError ? sim.error.messages : sim.error ? ["Erro inesperado ao simular."] : [];
  const fmtAlvo = formatDate(dData);

  return (
    <div className="space-y-5">
      <MarketStrip mercado={mercado} refreshing={refresh.isPending} onRefresh={() => refresh.mutate()} />

      <InputsBar
        valor={valor}
        dataAlvo={dataAlvo}
        minDate={amanha}
        onValor={(v) => {
          const m = maskBRL(v);
          setValor(m);
          writeStore(K_VALOR, m);
        }}
        onData={(d) => {
          setDataAlvo(d);
          if (d) writeStore(K_DATA, d);
        }}
      />

      {marketMsgs.length > 0 && (
        <div role="alert" className="rounded-xl border border-warn/30 bg-warn-bg px-3 py-2 text-sm text-warn">
          {marketMsgs.map((m) => (
            <p key={m}>{m}</p>
          ))}
        </div>
      )}

      {(erroValidacao || erroApi.length > 0) && (
        <div role="alert" className="rounded-xl border border-neg/30 bg-neg-bg px-3 py-2 text-sm text-neg">
          {(erroValidacao ? [erroValidacao] : erroApi).map((m) => (
            <p key={m}>{m}</p>
          ))}
        </div>
      )}

      <Filters value={filters} plataformas={plataformas} onChange={setFilters} />

      {sim.isPending && valido && <p className="py-10 text-center text-sm text-muted">Calculando…</p>}

      {data && (
        <div className={`space-y-8 transition-opacity ${sim.isFetching ? "opacity-60" : ""}`}>
          <section aria-label="Vencem até a sua data">
            <SectionHeader
              tone="pos"
              title="✅ Vencem até a sua data"
              count={verdes.length}
              hint={`Líquido em ${fmtAlvo}, do melhor para o pior`}
            />
            {verdes.length === 0 ? (
              <Empty>Nenhum produto vence até {fmtAlvo} com esses filtros.</Empty>
            ) : (
              <div className="grid gap-3 md:grid-cols-2">
                {verdes.map((r, i) => (
                  <ProductCard key={r.product.id} result={r} rank={i + 1} onSelect={setSelected} isentoTypes={isentos} />
                ))}
              </div>
            )}
          </section>

          <section aria-label="Vencem depois da sua data">
            <SectionHeader
              tone="neg"
              title="🔴 Vencem depois da sua data"
              count={vermelhos.length}
              hint="Exigem venda antecipada ou não podem ser resgatados na data"
            />
            {vermelhos.length === 0 ? (
              <Empty>Nada nesta seção com esses filtros.</Empty>
            ) : (
              <div className="grid gap-3 md:grid-cols-2">
                {vermelhos.map((r) => (
                  <ProductCard key={r.product.id} result={r} onSelect={setSelected} isentoTypes={isentos} />
                ))}
              </div>
            )}
          </section>

          {cinzas.length > 0 && (
            <section aria-label="Indisponíveis para este valor">
              <SectionHeader
                tone="off"
                title="Indisponíveis para este valor"
                count={cinzas.length}
                action={
                  <button
                    type="button"
                    aria-expanded={showOff}
                    aria-label={showOff ? "Recolher indisponíveis" : "Mostrar indisponíveis"}
                    onClick={() => setShowOff((s) => !s)}
                    className="rounded-full p-1.5 text-muted hover:text-ink"
                  >
                    <IconChevron open={showOff} />
                  </button>
                }
              />
              {showOff && (
                <div className="grid gap-3 md:grid-cols-2">
                  {cinzas.map((r) => (
                    <ProductCard key={r.product.id} result={r} onSelect={setSelected} isentoTypes={isentos} />
                  ))}
                </div>
              )}
            </section>
          )}
        </div>
      )}

      {selected && mercado && (
        <ProductDetail
          result={selected}
          mercado={mercado}
          isentoTypes={isentos}
          open
          onOpenChange={(o) => {
            if (!o) setSelected(null);
          }}
        />
      )}
    </div>
  );
}
