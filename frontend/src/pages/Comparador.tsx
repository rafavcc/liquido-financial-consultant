import { keepPreviousData, useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useEffect, useMemo, useState } from "react";
import { api, ApiError } from "../api/client";
import type { Horizonte, ProductType, SimulationResult } from "../api/types";
import { EMPTY_FILTERS, Filters, type FilterState } from "../components/Filters";
import { IconChevron } from "../components/Icons";
import { InputsBar } from "../components/InputsBar";
import { SortSelect } from "../components/SortSelect";
import { MarketStrip } from "../components/MarketStrip";
import { ProductCard } from "../components/ProductCard";
import { ProductDetail } from "../components/ProductDetail";
import { SectionHeader } from "../components/SectionHeader";
import { formatDate, maskBRL } from "../lib/format";
import { HORIZONTES, ISENTOS_PADRAO, isIsento, ORDENACOES, tipoGrupo } from "../lib/labels";
import { dominados, ordenar, type Ordenacao } from "../lib/ordering";
import { parseBRL } from "../lib/parse";
import { readStore, writeStore } from "../lib/storage";
import { useDebounced } from "../lib/useDebounced";

const K_VALOR = "liquido.valor";
const K_DATA = "liquido.dataAlvo";
const K_HORIZONTE = "liquido.horizonte";
const K_ORDENACAO = "liquido.ordenacao";

function readHorizonte(): Horizonte {
  const v = readStore(K_HORIZONTE);
  return HORIZONTES.some((h) => h.id === v) ? (v as Horizonte) : "DATA";
}
function readOrdenacao(h: Horizonte): Ordenacao {
  const v = readStore(K_ORDENACAO);
  const o: Ordenacao = ORDENACOES.some((x) => x.id === v) ? (v as Ordenacao) : "VALOR_LIQUIDO";
  return h === "SEM_DATA" && o === "VALOR_LIQUIDO" ? "TAXA" : o;
}

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
  const [horizonte, setHorizonteState] = useState<Horizonte>(readHorizonte);
  const [ordenacao, setOrdenacaoState] = useState<Ordenacao>(() => readOrdenacao(readHorizonte()));
  const [filters, setFilters] = useState<FilterState>(EMPTY_FILTERS);
  const [showOff, setShowOff] = useState(false);
  const [selected, setSelected] = useState<SimulationResult | null>(null);

  const hoje = isoDate(new Date());
  const amanha = isoDate(addDays(new Date(), 1));
  const dValor = useDebounced(valor, 400);
  const dData = useDebounced(dataAlvo, 400);

  const valorNum = parseBRL(dValor);
  const semData = horizonte === "SEM_DATA";
  const valido = valorNum !== null && Number(valorNum) > 0 && (horizonte !== "DATA" || dData > hoje);

  const setHorizonte = (h: Horizonte) => {
    setHorizonteState(h);
    writeStore(K_HORIZONTE, h);
    if (h === "SEM_DATA" && ordenacao === "VALOR_LIQUIDO") {
      setOrdenacaoState("TAXA");
      writeStore(K_ORDENACAO, "TAXA");
    }
  };
  const setOrdenacao = (o: Ordenacao) => {
    setOrdenacaoState(o);
    writeStore(K_ORDENACAO, o);
  };

  const sim = useQuery({
    queryKey: ["simulate", valorNum, horizonte, horizonte === "DATA" ? dData : null],
    queryFn: ({ signal }) => api.simulate(valorNum as string, horizonte, horizonte === "DATA" ? dData : null, signal),
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

  const { verdes, vermelhos, cinzas } = useMemo(() => {
    const secao = (list: SimulationResult[] | undefined) => {
      const filtrada = applyFilters(list ?? [], filters, isentos);
      return { dom: dominados(filtrada), lista: ordenar(filtrada, ordenacao) };
    };
    return { verdes: secao(data?.vence_ate_data), vermelhos: secao(data?.vence_depois), cinzas: secao(data?.indisponiveis) };
  }, [data, filters, isentos, ordenacao]);

  const erroValidacao =
    valorNum === null || Number(valorNum) <= 0
      ? "Informe um valor maior que zero."
      : horizonte === "DATA" && dData <= hoje
        ? "A data deve ser posterior a hoje."
        : null;
  const erroApi = sim.error instanceof ApiError ? sim.error.messages : sim.error ? ["Erro inesperado ao simular."] : [];
  // keepPreviousData: a resposta anterior só vale como "atual" quando é do horizonte selecionado.
  const atual = data !== undefined && data.horizonte === horizonte;
  const dataResolvida = atual ? data.data_alvo : null;
  const alvo = dataResolvida ?? (horizonte === "DATA" ? dData : null);
  const fmtAlvo = alvo ? formatDate(alvo) : "";

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
        horizonte={horizonte}
        onHorizonte={setHorizonte}
        dataResolvida={dataResolvida}
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

      <div className="flex flex-wrap items-center gap-2">
        <Filters value={filters} plataformas={plataformas} onChange={setFilters} />
        <SortSelect value={ordenacao} onChange={setOrdenacao} semData={semData} />
      </div>

      {sim.isPending && valido && <p className="py-10 text-center text-sm text-muted">Calculando…</p>}

      {data && (
        <div className={`space-y-8 transition-opacity ${sim.isFetching ? "opacity-60" : ""}`}>
          {data.horizonte === "SEM_DATA" ? (
            <section aria-label="Todos os produtos">
              <SectionHeader
                tone="pos"
                title="Todos os produtos — até o vencimento ou 1 ano"
                count={verdes.lista.length}
                hint="Taxa líquida a.a. de cada produto no seu prazo de saída"
              />
              {verdes.lista.length === 0 ? (
                <Empty>Nada nesta seção com esses filtros.</Empty>
              ) : (
                <div className="grid gap-3 md:grid-cols-2">
                  {verdes.lista.map((r, i) => (
                    <ProductCard key={r.product.id} result={r} rank={i + 1} destaque="taxa" dominado={verdes.dom.has(r.product.id)} hoje={hoje} onSelect={setSelected} isentoTypes={isentos} />
                  ))}
                </div>
              )}
            </section>
          ) : (
          <section aria-label="Vencem até a sua data">
            <SectionHeader
              tone="pos"
              title="✅ Vencem até a sua data"
              count={verdes.lista.length}
              hint={`Líquido em ${fmtAlvo}, ${ordenacao === "VALOR_LIQUIDO" ? "do melhor para o pior" : "na ordem escolhida"}`}
            />
            {verdes.lista.length === 0 ? (
              <Empty>Nenhum produto vence até {fmtAlvo} com esses filtros.</Empty>
            ) : (
              <div className="grid gap-3 md:grid-cols-2">
                {verdes.lista.map((r, i) => (
                  <ProductCard key={r.product.id} result={r} rank={i + 1} dominado={verdes.dom.has(r.product.id)} hoje={hoje} onSelect={setSelected} isentoTypes={isentos} />
                ))}
              </div>
            )}
          </section>
          )}

          {(data.horizonte !== "SEM_DATA" || vermelhos.lista.length > 0) && (
          <section aria-label="Vencem depois da sua data">
            <SectionHeader
              tone="neg"
              title="🔴 Vencem depois da sua data"
              count={vermelhos.lista.length}
              hint="Exigem venda antecipada ou não podem ser resgatados na data"
            />
            {vermelhos.lista.length === 0 ? (
              <Empty>Nada nesta seção com esses filtros.</Empty>
            ) : (
              <div className="grid gap-3 md:grid-cols-2">
                {vermelhos.lista.map((r) => (
                  <ProductCard key={r.product.id} result={r} dominado={vermelhos.dom.has(r.product.id)} hoje={hoje} onSelect={setSelected} isentoTypes={isentos} />
                ))}
              </div>
            )}
          </section>
          )}

          {cinzas.lista.length > 0 && (
            <section aria-label="Indisponíveis para este valor">
              <SectionHeader
                tone="off"
                title="Indisponíveis para este valor"
                count={cinzas.lista.length}
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
                  {cinzas.lista.map((r) => (
                    <ProductCard key={r.product.id} result={r} dominado={false} hoje={hoje} onSelect={setSelected} isentoTypes={isentos} />
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
