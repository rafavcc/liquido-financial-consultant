import * as Dialog from "@radix-ui/react-dialog";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { useId, useState, type ReactNode } from "react";
import { api, ApiError } from "../api/client";
import type { Indexer, Liquidity, ProductData, ProductType } from "../api/types";
import { maskBRL } from "../lib/format";
import { decimalToBRLInput, fractionToPercent, percentToFraction } from "../lib/percent";
import { parseBRL } from "../lib/parse";

interface Props {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  /** Sem produto = cadastro novo; com produto = edição (PUT). */
  product?: ProductData;
  /** Plataformas já usadas, oferecidas como sugestão junto com XP e BTG Pactual. */
  plataformas?: string[];
}

type TipoForm = Extract<ProductType, "CDB" | "LCI" | "LCA" | "LCD" | "CRI" | "CRA" | "FUNDO_RF">;

const TIPOS: { id: TipoForm; label: string }[] = [
  { id: "CDB", label: "CDB" },
  { id: "LCI", label: "LCI" },
  { id: "LCA", label: "LCA" },
  { id: "LCD", label: "LCD" },
  { id: "CRI", label: "CRI" },
  { id: "CRA", label: "CRA" },
  { id: "FUNDO_RF", label: "Fundo RF" },
];

const SEM_LIQUIDEZ_DIARIA: TipoForm[] = ["LCI", "LCA", "LCD"];

const INDEXADORES: { id: Indexer; label: string }[] = [
  { id: "PRE", label: "Prefixado" },
  { id: "PCT_CDI", label: "% do CDI" },
  { id: "CDI_MAIS", label: "CDI +" },
  { id: "IPCA_MAIS", label: "IPCA +" },
  { id: "SELIC", label: "Selic +" },
];
const INDEXADORES_FUNDO: Indexer[] = ["PCT_CDI", "CDI_MAIS"];

const LIQUIDEZ: { id: Liquidity; label: string }[] = [
  { id: "NO_VENCIMENTO", label: "No vencimento" },
  { id: "DIARIA", label: "Diária" },
  { id: "DIARIA_APOS_CARENCIA", label: "Diária após carência" },
];

/** Prefixo/sufixo visíveis do campo taxa, por indexador. */
const TAXA_UI: Record<Indexer, { prefix?: string; suffix: string }> = {
  PCT_CDI: { suffix: "% do CDI" },
  PRE: { suffix: "% a.a." },
  CDI_MAIS: { prefix: "CDI +", suffix: "% a.a." },
  IPCA_MAIS: { prefix: "IPCA +", suffix: "% a.a." },
  SELIC: { prefix: "Selic +", suffix: "% a.a." },
};

const PLATAFORMAS_BASE = ["XP", "BTG Pactual"];

interface FormState {
  tipo: TipoForm;
  nome: string;
  emissor: string;
  plataforma: string;
  indexador: Indexer;
  taxa: string;
  data_vencimento: string;
  valor_minimo: string;
  liquidez: Liquidity;
  data_carencia: string;
  observacoes: string;
  taxa_adm: string;
  prazo_resgate_dias: string;
  classe_tributaria: "LONGO" | "CURTO";
}

const EMPTY: FormState = {
  tipo: "CDB", nome: "", emissor: "", plataforma: "", indexador: "PCT_CDI", taxa: "", data_vencimento: "",
  valor_minimo: "", liquidez: "NO_VENCIMENTO", data_carencia: "", observacoes: "", taxa_adm: "",
  prazo_resgate_dias: "", classe_tributaria: "LONGO",
};

function fromProduct(p: ProductData): FormState {
  const fundo = p.tipo === "FUNDO_RF";
  return {
    tipo: (TIPOS.some((t) => t.id === p.tipo) ? p.tipo : "CDB") as TipoForm,
    nome: p.nome,
    emissor: p.emissor,
    plataforma: p.plataforma,
    indexador: p.indexador,
    taxa: fractionToPercent(p.taxa),
    data_vencimento: p.data_vencimento ?? "",
    valor_minimo: decimalToBRLInput(p.valor_minimo),
    liquidez: fundo ? "NO_VENCIMENTO" : p.liquidez,
    data_carencia: p.data_carencia ?? "",
    observacoes: p.observacoes,
    taxa_adm: fractionToPercent(p.taxa_adm),
    prazo_resgate_dias: p.prazo_resgate_dias === null ? "" : String(p.prazo_resgate_dias),
    classe_tributaria: p.classe_tributaria ?? "LONGO",
  };
}

const OBRIGATORIO = "Campo obrigatório";

/** Valida o mínimo para montar o payload; o resto (faixas, carência mínima) é do backend. */
function build(f: FormState, base?: ProductData): { body?: Partial<ProductData>; errors: Record<string, string> } {
  const errors: Record<string, string> = {};
  const fundo = f.tipo === "FUNDO_RF";
  if (!f.nome.trim()) errors.nome = OBRIGATORIO;
  if (!f.emissor.trim()) errors.emissor = OBRIGATORIO;
  if (!f.plataforma.trim()) errors.plataforma = OBRIGATORIO;

  const taxa = percentToFraction(f.taxa);
  if (!f.taxa.trim()) errors.taxa = OBRIGATORIO;
  else if (taxa === null) errors.taxa = "Informe um número, como 112 ou 14,2";

  // Campo intocado: reenvia o original (o campo só exibe 2 casas e truncaria o valor).
  const minimoIntocado = base !== undefined && f.valor_minimo === decimalToBRLInput(base.valor_minimo);
  const minimo = minimoIntocado ? base.valor_minimo : f.valor_minimo.trim() === "" ? "0" : parseBRL(f.valor_minimo);
  if (minimo === null) errors.valor_minimo = "Valor inválido";

  let taxaAdm: string | null = null;
  let prazo: number | null = null;
  if (fundo) {
    if (!f.taxa_adm.trim()) errors.taxa_adm = OBRIGATORIO;
    else {
      taxaAdm = percentToFraction(f.taxa_adm);
      if (taxaAdm === null) errors.taxa_adm = "Informe um número, como 0,30";
    }
    if (!f.prazo_resgate_dias.trim()) errors.prazo_resgate_dias = OBRIGATORIO;
    else if (!/^\d+$/.test(f.prazo_resgate_dias.trim())) errors.prazo_resgate_dias = "Informe dias inteiros";
    else prazo = Number(f.prazo_resgate_dias.trim());
  } else {
    if (!f.data_vencimento) errors.data_vencimento = OBRIGATORIO;
    if (f.liquidez === "DIARIA_APOS_CARENCIA" && !f.data_carencia) errors.data_carencia = OBRIGATORIO;
  }
  if (Object.keys(errors).length > 0) return { errors };

  const carencia = !fundo && f.liquidez === "DIARIA_APOS_CARENCIA" ? f.data_carencia : null;
  const body: Partial<ProductData> = {
    ...(base ? { id: base.id, ativo: base.ativo, exemplo: base.exemplo } : {}),
    // Cobertura só se mantém quando o tipo não mudou; senão o backend deriva do novo tipo.
    ...(base && base.tipo === f.tipo ? { cobertura: base.cobertura } : {}),
    tipo: f.tipo,
    nome: f.nome.trim(),
    emissor: f.emissor.trim(),
    plataforma: f.plataforma.trim(),
    indexador: f.indexador,
    taxa: taxa as string,
    data_vencimento: fundo ? null : f.data_vencimento,
    valor_minimo: minimo as string,
    liquidez: fundo ? "DIARIA" : f.liquidez,
    data_carencia: carencia,
    observacoes: f.observacoes.trim(),
    taxa_adm: fundo ? taxaAdm : null,
    prazo_resgate_dias: fundo ? prazo : null,
    classe_tributaria: fundo ? f.classe_tributaria : null,
  };
  return { body, errors };
}

/** Mensagens "campo: texto" do backend viram erro do campo; as demais ficam só no topo. */
function fieldErrorsFrom(messages: string[]): Record<string, string> {
  const out: Record<string, string> = {};
  for (const m of messages) {
    const hit = /^([a-z_]+):\s*(.+)$/.exec(m);
    if (hit && !(hit[1] in out)) out[hit[1]] = hit[2];
  }
  return out;
}

function isoTomorrow(): string {
  const d = new Date();
  d.setDate(d.getDate() + 1);
  const p = (n: number) => String(n).padStart(2, "0");
  return `${d.getFullYear()}-${p(d.getMonth() + 1)}-${p(d.getDate())}`;
}

const inputCls = (err?: string) =>
  `w-full rounded-xl border bg-surface px-3 py-2.5 text-base text-ink placeholder:text-muted/60 focus:border-accent focus:outline-none sm:text-sm ${
    err ? "border-neg" : "border-line"
  }`;

interface FieldProps {
  label: string;
  error?: string;
  hint?: string;
  className?: string;
  children: (id: string, describedBy: string | undefined) => ReactNode;
}

function Field({ label, error, hint, className = "", children }: FieldProps) {
  const id = useId();
  const msgId = `${id}-msg`;
  const message = error ?? hint;
  return (
    <div className={className}>
      <label htmlFor={id} className="mb-1 block text-xs font-medium text-muted">
        {label}
      </label>
      {children(id, message ? msgId : undefined)}
      {message && (
        <p id={msgId} className={`mt-1 text-xs ${error ? "text-neg" : "text-muted"}`}>
          {message}
        </p>
      )}
    </div>
  );
}

/** Campo numérico com prefixo (ex. "IPCA +") e sufixo (ex. "% a.a.") dentro da caixa. */
function Affixed({
  prefix, suffix, children,
}: { prefix?: string; suffix: string; children: (padding: string) => ReactNode }) {
  return (
    <div className="relative">
      {prefix && (
        <span className="pointer-events-none absolute inset-y-0 left-3 flex items-center text-sm text-muted">{prefix}</span>
      )}
      {children(prefix ? "pl-[4.25rem]" : "")}
      <span className="pointer-events-none absolute inset-y-0 right-3 flex items-center text-sm text-muted">{suffix}</span>
    </div>
  );
}

export function ProductForm({ open, onOpenChange, product, plataformas = [] }: Props) {
  const qc = useQueryClient();
  const [f, setF] = useState<FormState>(() => (product ? fromProduct(product) : EMPTY));
  const [fieldErrors, setFieldErrors] = useState<Record<string, string>>({});
  const [topErrors, setTopErrors] = useState<string[]>([]);
  const listId = useId();
  const fundo = f.tipo === "FUNDO_RF";
  const editando = product !== undefined;

  const set = <K extends keyof FormState>(k: K, v: FormState[K]) => {
    setF((s) => ({ ...s, [k]: v }));
    setFieldErrors((e) => (k in e ? Object.fromEntries(Object.entries(e).filter(([key]) => key !== k)) : e));
  };

  const save = useMutation({
    mutationFn: (body: Partial<ProductData>) =>
      product ? api.products.update(product.id, body) : api.products.create(body),
    onSuccess: () => {
      void qc.invalidateQueries({ queryKey: ["products"] });
      void qc.invalidateQueries({ queryKey: ["simulate"] });
      onOpenChange(false);
    },
    onError: (e) => {
      const msgs = e instanceof ApiError ? e.messages : ["Não foi possível salvar o produto."];
      setTopErrors(msgs);
      setFieldErrors((prev) => ({ ...prev, ...fieldErrorsFrom(msgs) }));
    },
  });

  const onTipo = (tipo: TipoForm) => {
    setTopErrors([]);
    setFieldErrors({});
    setF((s) => ({
      ...s,
      tipo,
      indexador: tipo === "FUNDO_RF" && !INDEXADORES_FUNDO.includes(s.indexador) ? "PCT_CDI" : s.indexador,
      liquidez: SEM_LIQUIDEZ_DIARIA.includes(tipo) && s.liquidez === "DIARIA" ? "NO_VENCIMENTO" : s.liquidez,
    }));
  };

  const submit = (e: React.FormEvent) => {
    e.preventDefault();
    setTopErrors([]);
    const { body, errors } = build(f, product);
    setFieldErrors(errors);
    if (body) save.mutate(body);
  };

  const indexadores = INDEXADORES.filter((i) => !fundo || INDEXADORES_FUNDO.includes(i.id));
  const liquidezOpts = LIQUIDEZ.filter((l) => !(l.id === "DIARIA" && SEM_LIQUIDEZ_DIARIA.includes(f.tipo)));
  const taxaUi = TAXA_UI[f.indexador];
  const sugestoes = [...new Set([...PLATAFORMAS_BASE, ...plataformas])].filter((p) => p !== "Tesouro Direto");

  return (
    <Dialog.Root open={open} onOpenChange={(o) => !save.isPending && onOpenChange(o)}>
      <Dialog.Portal>
        <Dialog.Overlay className="detail-overlay fixed inset-0 z-40 bg-black/50" />
        <Dialog.Content
          className="detail-content fixed inset-0 z-50 flex flex-col overflow-hidden bg-surface text-ink shadow-xl
            sm:left-auto sm:w-[520px] sm:border-l sm:border-line"
        >
          <header className="flex items-start justify-between gap-3 border-b border-line px-5 pb-4 pt-5">
            <div className="min-w-0">
              <Dialog.Title className="text-lg font-semibold leading-tight">
                {editando ? "Editar produto" : "Novo produto"}
              </Dialog.Title>
              <Dialog.Description className="mt-1 text-sm text-muted">
                Cadastre a oferta como aparece na plataforma. Taxas em %, como você lê no app.
              </Dialog.Description>
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

          <form onSubmit={submit} noValidate className="flex min-h-0 flex-1 flex-col">
            <div className="flex-1 space-y-4 overflow-y-auto px-5 py-5">
              {topErrors.length > 0 && (
                <div role="alert" className="rounded-xl border border-neg/30 bg-neg-bg px-3 py-2 text-sm text-neg">
                  {topErrors.map((m) => (
                    <p key={m}>{m}</p>
                  ))}
                </div>
              )}

              <div className="grid grid-cols-2 gap-3">
                <Field label="Tipo" error={fieldErrors.tipo}>
                  {(id) => (
                    <select id={id} value={f.tipo} onChange={(e) => onTipo(e.target.value as TipoForm)} className={inputCls()}>
                      {TIPOS.map((t) => (
                        <option key={t.id} value={t.id}>{t.label}</option>
                      ))}
                    </select>
                  )}
                </Field>
                <Field label="Indexador" error={fieldErrors.indexador}>
                  {(id) => (
                    <select id={id} value={f.indexador} onChange={(e) => set("indexador", e.target.value as Indexer)} className={inputCls(fieldErrors.indexador)}>
                      {indexadores.map((i) => (
                        <option key={i.id} value={i.id}>{i.label}</option>
                      ))}
                    </select>
                  )}
                </Field>
              </div>

              <Field label="Nome" error={fieldErrors.nome}>
                {(id, d) => (
                  <input id={id} aria-describedby={d} aria-invalid={!!fieldErrors.nome} value={f.nome} onChange={(e) => set("nome", e.target.value)}
                    placeholder={fundo ? "Ex.: Fundo Alfa Renda Fixa DI" : "Ex.: CDB Banco Alfa 2029"} className={inputCls(fieldErrors.nome)} />
                )}
              </Field>

              <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
                <Field label="Emissor" error={fieldErrors.emissor}>
                  {(id, d) => (
                    <input id={id} aria-describedby={d} aria-invalid={!!fieldErrors.emissor} value={f.emissor} onChange={(e) => set("emissor", e.target.value)}
                      placeholder={fundo ? "Gestora" : "Banco ou securitizadora"} className={inputCls(fieldErrors.emissor)} />
                  )}
                </Field>
                <Field label="Plataforma" error={fieldErrors.plataforma}>
                  {(id, d) => (
                    <>
                      <input id={id} aria-describedby={d} aria-invalid={!!fieldErrors.plataforma} list={listId} value={f.plataforma}
                        onChange={(e) => set("plataforma", e.target.value)} placeholder="Onde você investe" autoComplete="off"
                        className={inputCls(fieldErrors.plataforma)} />
                      <datalist id={listId}>
                        {sugestoes.map((p) => (
                          <option key={p} value={p} />
                        ))}
                      </datalist>
                    </>
                  )}
                </Field>
              </div>

              <div className="grid grid-cols-2 gap-3">
                <Field label="Taxa" error={fieldErrors.taxa}>
                  {(id, d) => (
                    <Affixed prefix={taxaUi.prefix} suffix={taxaUi.suffix}>
                      {(pad) => (
                        <input id={id} aria-describedby={d} aria-invalid={!!fieldErrors.taxa} inputMode="decimal" value={f.taxa}
                          onChange={(e) => set("taxa", e.target.value)} placeholder={f.indexador === "PCT_CDI" ? "112" : "14,2"}
                          className={`${inputCls(fieldErrors.taxa)} ${pad} ${taxaUi.suffix.length > 6 ? "pr-20" : "pr-14"}`} />
                      )}
                    </Affixed>
                  )}
                </Field>
                <Field label="Valor mínimo" error={fieldErrors.valor_minimo}>
                  {(id, d) => (
                    <div className="relative">
                      <span className="pointer-events-none absolute inset-y-0 left-3 flex items-center text-sm text-muted">R$</span>
                      <input id={id} aria-describedby={d} aria-invalid={!!fieldErrors.valor_minimo} inputMode="decimal" value={f.valor_minimo}
                        onChange={(e) => set("valor_minimo", maskBRL(e.target.value))} placeholder="0"
                        className={`${inputCls(fieldErrors.valor_minimo)} pl-10`} />
                    </div>
                  )}
                </Field>
              </div>

              {fundo ? (
                <>
                  <div className="grid grid-cols-2 gap-3">
                    <Field label="Taxa de administração" error={fieldErrors.taxa_adm}>
                      {(id, d) => (
                        <Affixed suffix="% a.a.">
                          {() => (
                            <input id={id} aria-describedby={d} aria-invalid={!!fieldErrors.taxa_adm} inputMode="decimal" value={f.taxa_adm}
                              onChange={(e) => set("taxa_adm", e.target.value)} placeholder="0,30" className={`${inputCls(fieldErrors.taxa_adm)} pr-14`} />
                          )}
                        </Affixed>
                      )}
                    </Field>
                    <Field label="Prazo de resgate" error={fieldErrors.prazo_resgate_dias}>
                      {(id, d) => (
                        <div className="relative">
                          <span className="pointer-events-none absolute inset-y-0 left-3 flex items-center text-sm text-muted">D+</span>
                          <input id={id} aria-describedby={d} aria-invalid={!!fieldErrors.prazo_resgate_dias} inputMode="numeric" value={f.prazo_resgate_dias}
                            onChange={(e) => set("prazo_resgate_dias", e.target.value.replace(/\D/g, ""))} placeholder="1"
                            className={`${inputCls(fieldErrors.prazo_resgate_dias)} pl-9 pr-14`} />
                          <span className="pointer-events-none absolute inset-y-0 right-3 flex items-center text-sm text-muted">dias</span>
                        </div>
                      )}
                    </Field>
                  </div>
                  <Field label="Classe tributária" error={fieldErrors.classe_tributaria} hint="Define a alíquota do come-cotas, configurável em Configurações.">
                    {(id, d) => (
                      <select id={id} aria-describedby={d} value={f.classe_tributaria} onChange={(e) => set("classe_tributaria", e.target.value as "LONGO" | "CURTO")} className={inputCls()}>
                        <option value="LONGO">Longo prazo</option>
                        <option value="CURTO">Curto prazo</option>
                      </select>
                    )}
                  </Field>
                </>
              ) : (
                <>
                  <Field label="Vencimento" error={fieldErrors.data_vencimento}>
                    {(id, d) => (
                      <input id={id} aria-describedby={d} aria-invalid={!!fieldErrors.data_vencimento} type="date" min={isoTomorrow()} value={f.data_vencimento}
                        onChange={(e) => set("data_vencimento", e.target.value)} className={inputCls(fieldErrors.data_vencimento)} />
                    )}
                  </Field>
                  <div className={`grid gap-3 ${f.liquidez === "DIARIA_APOS_CARENCIA" ? "grid-cols-2" : "grid-cols-1"}`}>
                    <Field label="Liquidez" error={fieldErrors.liquidez}>
                      {(id, d) => (
                        <select id={id} aria-describedby={d} value={f.liquidez} onChange={(e) => set("liquidez", e.target.value as Liquidity)} className={inputCls(fieldErrors.liquidez)}>
                          {liquidezOpts.map((l) => (
                            <option key={l.id} value={l.id}>{l.label}</option>
                          ))}
                        </select>
                      )}
                    </Field>
                    {f.liquidez === "DIARIA_APOS_CARENCIA" && (
                      <Field label="Data de carência" error={fieldErrors.data_carencia}>
                        {(id, d) => (
                          <input id={id} aria-describedby={d} aria-invalid={!!fieldErrors.data_carencia} type="date" min={isoTomorrow()} value={f.data_carencia}
                            onChange={(e) => set("data_carencia", e.target.value)} className={inputCls(fieldErrors.data_carencia)} />
                        )}
                      </Field>
                    )}
                  </div>
                </>
              )}

              <Field label="Observações" error={fieldErrors.observacoes}>
                {(id, d) => (
                  <textarea id={id} aria-describedby={d} rows={2} value={f.observacoes} onChange={(e) => set("observacoes", e.target.value)}
                    placeholder="Opcional" className={`${inputCls(fieldErrors.observacoes)} resize-none`} />
                )}
              </Field>
            </div>

            <footer className="flex items-center justify-end gap-2 border-t border-line bg-surface px-5 py-3 pb-[max(0.75rem,env(safe-area-inset-bottom))]">
              <Dialog.Close
                type="button"
                className="rounded-xl border border-line px-4 py-2.5 text-sm font-medium text-muted hover:text-ink"
              >
                Cancelar
              </Dialog.Close>
              <button
                type="submit"
                disabled={save.isPending}
                className="rounded-xl bg-accent px-5 py-2.5 text-sm font-semibold text-accent-fg transition hover:opacity-90 disabled:opacity-60"
              >
                {save.isPending ? "Salvando…" : "Salvar"}
              </button>
            </footer>
          </form>
        </Dialog.Content>
      </Dialog.Portal>
    </Dialog.Root>
  );
}
