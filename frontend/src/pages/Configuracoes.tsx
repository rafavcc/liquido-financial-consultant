import * as Dialog from "@radix-ui/react-dialog";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useEffect, useId, useMemo, useRef, useState, type ReactNode } from "react";
import { api, ApiError } from "../api/client";
import type { ProductType, Settings } from "../api/types";
import { IconChevron, IconPlus, IconRefresh, IconTrash } from "../components/Icons";
import { formatDateTime } from "../lib/format";
import {
  buildSettings, fieldGroup, PRAZOS, fieldLabel, isDirty, parseServerError, TIPOS_MANUAIS, TIPOS_TESOURO, toForm,
  type GrupoId, type SettingsForm,
} from "../lib/settingsForm";
import { tipoLabel } from "../lib/labels";

const FONTES: { id: string; label: string }[] = [
  { id: "bcb", label: "Banco Central" },
  { id: "focus", label: "Focus" },
  { id: "tesouro", label: "Tesouro Direto" },
];

const inputCls = (err?: boolean) =>
  `w-full rounded-xl border bg-surface px-3 py-2.5 text-base text-ink placeholder:text-muted/60 focus:border-accent focus:outline-none sm:text-sm ${
    err ? "border-neg" : "border-line"
  }`;

interface BoxProps {
  label: string;
  value: string;
  onChange: (v: string) => void;
  suffix?: string;
  error?: string;
  hint?: string;
  inputMode?: "decimal" | "numeric";
  className?: string;
}

/** Campo de texto com sufixo (%, R$, h) e mensagem de erro/ajuda; o rótulo é lido por leitores de tela. */
function Box({ label, value, onChange, suffix, error, hint, inputMode = "decimal", className = "" }: BoxProps) {
  const id = useId();
  return (
    <div className={className}>
      <label htmlFor={id} className="mb-1 block text-sm font-medium">{label}</label>
      <div className="relative">
        <input
          id={id}
          value={value}
          onChange={(e) => onChange(e.target.value)}
          inputMode={inputMode}
          autoComplete="off"
          aria-invalid={error ? true : undefined}
          aria-describedby={error || hint ? `${id}-msg` : undefined}
          className={`${inputCls(!!error)} ${suffix ? "pr-14" : ""}`}
        />
        {suffix && <span className="pointer-events-none absolute inset-y-0 right-3 flex items-center text-sm text-muted">{suffix}</span>}
      </div>
      {(error || hint) && (
        <p id={`${id}-msg`} className={`mt-1 text-xs ${error ? "text-neg" : "text-muted"}`}>{error ?? hint}</p>
      )}
    </div>
  );
}

/** Célula compacta (sem rótulo visível) para tabelas; o nome acessível vem de `label`. */
function Cell({ label, value, onChange, suffix, error, inputMode = "decimal" }: Omit<BoxProps, "hint" | "className">) {
  return (
    <div className="relative">
      <input
        aria-label={label}
        value={value}
        onChange={(e) => onChange(e.target.value)}
        inputMode={inputMode}
        autoComplete="off"
        aria-invalid={error ? true : undefined}
        title={error}
        className={`${inputCls(!!error)} ${suffix ? "pr-8" : ""} px-2.5 py-2`}
      />
      {suffix && <span className="pointer-events-none absolute inset-y-0 right-2.5 flex items-center text-xs text-muted">{suffix}</span>}
    </div>
  );
}

interface GroupProps {
  id: GrupoId;
  title: string;
  help: string;
  errors: { path: string; message: string }[];
  localInvalid: boolean;
  children: ReactNode;
}

function Group({ id, title, help, errors, localInvalid, children }: GroupProps) {
  const mine = errors.filter((e) => fieldGroup(e.path) === id);
  return (
    <section aria-labelledby={`g-${id}`} className="rounded-2xl border border-line bg-surface p-4 shadow-card sm:p-5">
      <h2 id={`g-${id}`} className="text-base font-semibold">{title}</h2>
      <p className="mt-0.5 text-sm text-muted">{help}</p>
      {(mine.length > 0 || localInvalid) && (
        <div className="mt-3 rounded-xl border border-neg/30 bg-neg-bg px-3 py-2 text-sm text-neg">
          {mine.map((e) => (
            <p key={`${e.path}${e.message}`}>{e.message}</p>
          ))}
          {mine.length === 0 && <p>Corrija os campos destacados em vermelho.</p>}
        </div>
      )}
      <div className="mt-4 space-y-5">{children}</div>
    </section>
  );
}

const SubTitle = ({ children, help }: { children: ReactNode; help?: string }) => (
  <div>
    <h3 className="text-sm font-semibold">{children}</h3>
    {help && <p className="mt-0.5 text-xs text-muted">{help}</p>}
  </div>
);

function Check({ label, checked, indeterminate, onChange }: { label: string; checked: boolean; indeterminate?: boolean; onChange: (v: boolean) => void }) {
  const ref = useRef<HTMLInputElement>(null);
  useEffect(() => {
    if (ref.current) ref.current.indeterminate = !!indeterminate;
  }, [indeterminate]);
  return (
    <label className="flex cursor-pointer items-center gap-2 rounded-lg border border-line px-3 py-2 text-sm has-[:checked]:border-accent/60 has-[:checked]:bg-subtle">
      <input ref={ref} type="checkbox" checked={checked} onChange={(e) => onChange(e.target.checked)} className="h-4 w-4 accent-[rgb(var(--accent))]" />
      {label}
    </label>
  );
}

const TIPO_CHECK_LABEL: Partial<Record<ProductType, string>> = { FUNDO_RF: "Fundos de renda fixa" };

function Exempt({ legend, value, onChange }: { legend: string; value: ProductType[]; onChange: (v: ProductType[]) => void }) {
  const toggle = (t: ProductType, on: boolean) => onChange(on ? [...value.filter((x) => x !== t), t] : value.filter((x) => x !== t));
  const tesouroOn = TIPOS_TESOURO.filter((t) => value.includes(t)).length;
  const setTesouro = (on: boolean) => onChange(on ? [...value.filter((t) => !TIPOS_TESOURO.includes(t)), ...TIPOS_TESOURO] : value.filter((t) => !TIPOS_TESOURO.includes(t)));
  return (
    <fieldset aria-label={legend}>
      <legend className="mb-2 text-sm font-semibold">{legend}</legend>
      <div className="grid grid-cols-2 gap-2 sm:grid-cols-4">
        {TIPOS_MANUAIS.map((t) => (
          <Check key={t} label={TIPO_CHECK_LABEL[t] ?? tipoLabel(t)} checked={value.includes(t)} onChange={(on) => toggle(t, on)} />
        ))}
        <Check
          label="Tesouro Direto"
          checked={tesouroOn === TIPOS_TESOURO.length}
          indeterminate={tesouroOn > 0 && tesouroOn < TIPOS_TESOURO.length}
          onChange={setTesouro}
        />
      </div>
    </fieldset>
  );
}

function ConfirmReset({ open, pending, onCancel, onConfirm }: { open: boolean; pending: boolean; onCancel: () => void; onConfirm: () => void }) {
  return (
    <Dialog.Root open={open} onOpenChange={(o) => !o && !pending && onCancel()}>
      <Dialog.Portal>
        <Dialog.Overlay className="detail-overlay fixed inset-0 z-40 bg-black/50" />
        <Dialog.Content className="detail-content fixed left-1/2 top-1/2 z-50 w-[calc(100%-2rem)] max-w-sm -translate-x-1/2 -translate-y-1/2 rounded-2xl border border-line bg-surface p-5 text-ink shadow-xl">
          <Dialog.Title className="text-base font-semibold">Restaurar padrões?</Dialog.Title>
          <Dialog.Description className="mt-1.5 text-sm text-muted">
            Todas as configurações voltam aos valores originais (alíquotas, custos, projeções e limites). Seus produtos não são afetados.
          </Dialog.Description>
          <div className="mt-5 flex justify-end gap-2">
            <Dialog.Close className="rounded-xl border border-line px-4 py-2 text-sm font-medium text-muted hover:text-ink">Cancelar</Dialog.Close>
            <button type="button" disabled={pending} onClick={onConfirm} className="rounded-xl bg-neg px-4 py-2 text-sm font-semibold text-white hover:opacity-90 disabled:opacity-60">
              {pending ? "Restaurando…" : "Restaurar"}
            </button>
          </div>
        </Dialog.Content>
      </Dialog.Portal>
    </Dialog.Root>
  );
}

const errMessages = (e: unknown): string[] => (e instanceof ApiError ? e.messages : ["Não foi possível concluir a operação."]);

export function Configuracoes() {
  const qc = useQueryClient();
  const settingsQ = useQuery({ queryKey: ["settings"], queryFn: api.settings.get, retry: false });
  const marketQ = useQuery({ queryKey: ["market"], queryFn: api.market, retry: false });
  const orig = settingsQ.data;

  const [edited, setEdited] = useState<SettingsForm | null>(null);
  const [serverErrors, setServerErrors] = useState<string[]>([]);
  const [actionError, setActionError] = useState<string[]>([]);
  const [showIof, setShowIof] = useState(false);
  const [confirmReset, setConfirmReset] = useState(false);

  const form = useMemo(() => edited ?? (orig ? toForm(orig) : null), [edited, orig]);
  const built = useMemo(() => (form && orig ? buildSettings(form, orig) : null), [form, orig]);

  const refreshAll = () => {
    for (const k of ["settings", "simulate", "market"]) void qc.invalidateQueries({ queryKey: [k] });
  };
  const adopt = (s: Settings) => {
    qc.setQueryData(["settings"], s);
    setEdited(null);
    setServerErrors([]);
    setActionError([]);
    refreshAll();
  };

  const save = useMutation({ mutationFn: api.settings.update, onSuccess: adopt, onError: (e) => setServerErrors(errMessages(e)) });
  const reset = useMutation({
    mutationFn: api.settings.reset,
    onSuccess: (s) => { setConfirmReset(false); adopt(s); },
    onError: (e) => { setConfirmReset(false); setActionError(errMessages(e)); },
  });
  const refresh = useMutation({
    mutationFn: api.refreshMarket,
    onSuccess: () => { setActionError([]); refreshAll(); },
    onError: (e) => setActionError(errMessages(e)),
  });

  if (settingsQ.isPending) return <p className="py-16 text-center text-sm text-muted">Carregando configurações…</p>;
  if (!orig || !form || !built) {
    return (
      <div role="alert" className="rounded-xl border border-neg/30 bg-neg-bg px-3 py-2 text-sm text-neg">
        {errMessages(settingsQ.error).join(" ")}
      </div>
    );
  }

  const edit = (patch: Partial<SettingsForm>) => {
    setServerErrors([]);
    setActionError([]);
    setEdited({ ...form, ...patch });
  };
  const { errors } = built;
  const invalid = Object.keys(errors).length > 0;
  const dirty = invalid || isDirty(built.settings, orig);
  const canSave = dirty && !invalid && !save.isPending;
  const server = serverErrors.map(parseServerError);
  const serverFor = (path: string) => server.find((e) => e.path === path)?.message;
  const err = (path: string) => errors[path] ?? serverFor(path);
  const localIn = (g: GrupoId) => Object.keys(errors).some((p) => fieldGroup(p) === g);

  const setIr = (i: number, patch: Partial<SettingsForm["ir"][number]>) => edit({ ir: form.ir.map((r, j) => (j === i ? { ...r, ...patch } : r)) });
  const setRow = (i: number, patch: Partial<SettingsForm["rows"][number]>) => edit({ rows: form.rows.map((r, j) => (j === i ? { ...r, ...patch } : r)) });
  const setMode = (mode: SettingsForm["mode"]) =>
    edit({ mode, rows: mode === "manual" && form.rows.length === 0 ? [{ ano: String(new Date().getFullYear()), selic: "", ipca: "" }] : form.rows });
  const addRow = () => {
    const last = Math.max(0, ...form.rows.map((r) => Number(r.ano) || 0));
    edit({ rows: [...form.rows, { ano: String((last || new Date().getFullYear() - 1) + 1), selic: "", ipca: "" }] });
  };

  const market = marketQ.data;
  const top = server;

  return (
    <div className="space-y-5 pb-24 sm:pb-2">
      <div className="flex items-start justify-between gap-3">
        <div>
          <h1 className="text-xl font-semibold tracking-tight">Configurações</h1>
          <p className="mt-0.5 text-sm text-muted">Regras de imposto, custos e projeções usadas em todas as comparações.</p>
        </div>
        <button
          type="button"
          onClick={() => setConfirmReset(true)}
          className="shrink-0 rounded-xl border border-line px-3 py-2 text-sm font-medium text-muted transition hover:text-ink"
        >
          Restaurar padrões
        </button>
      </div>

      {actionError.length > 0 && (
        <div role="alert" aria-label="Erro na operação" className="rounded-xl border border-neg/30 bg-neg-bg px-3 py-2 text-sm text-neg">
          {actionError.map((m) => (
            <p key={m}>{m}</p>
          ))}
        </div>
      )}

      {top.length > 0 && (
        <div role="alert" aria-label="Erros ao salvar" className="rounded-xl border border-neg/30 bg-neg-bg px-3 py-2 text-sm text-neg">
          <p className="font-semibold">Não foi possível salvar. Revise:</p>
          <ul className="mt-1 list-disc pl-5">
            {top.map((e) => (
              <li key={`${e.path}${e.message}`}>
                {e.path && <strong className="font-semibold">{fieldLabel(e.path)}:</strong>} <span>{e.message}</span>
              </li>
            ))}
          </ul>
        </div>
      )}

      <Group id="tributacao" title="Tributação" localInvalid={localIn("tributacao")} errors={server}
        help="Alíquotas de Imposto de Renda e IOF aplicadas sobre o rendimento. Os padrões seguem a tabela regressiva vigente.">
        <div>
          <SubTitle help="Prazos contados em dias corridos desde a aplicação. A última faixa vale para qualquer prazo acima do limite anterior.">
            Imposto de Renda (tabela regressiva)
          </SubTitle>
          <div className="mt-3 divide-y divide-line rounded-xl border border-line">
            {form.ir.map((row, i) => {
              const last = i === form.ir.length - 1;
              const prev = form.ir[i - 1]?.max;
              const rateErr = err(`ir_brackets.${i}.rate`);
              const maxErr = err(`ir_brackets.${i}.max_days`);
              return (
                <div key={i} className="grid grid-cols-[1fr_auto_auto] items-center gap-3 px-3 py-2.5">
                  {last ? (
                    <span className="text-sm">Acima de {prev} dias</span>
                  ) : (
                    <div className="flex items-center gap-2 text-sm">
                      <span>Até</span>
                      <div className="w-20">
                        <Cell label={`Limite da faixa ${i + 1} de IR (dias)`} value={row.max} inputMode="numeric" error={maxErr} onChange={(v) => setIr(i, { max: v })} />
                      </div>
                      <span>dias</span>
                    </div>
                  )}
                  <span className="hidden text-xs text-muted sm:inline">alíquota</span>
                  <div className="w-24">
                    <Cell
                      label={last ? `Alíquota de IR acima de ${prev} dias` : `Alíquota de IR até ${row.max} dias`}
                      value={row.rate}
                      suffix="%"
                      error={rateErr}
                      onChange={(v) => setIr(i, { rate: v })}
                    />
                  </div>
                </div>
              );
            })}
          </div>
        </div>

        <div>
          <button
            type="button"
            aria-expanded={showIof}
            onClick={() => setShowIof((s) => !s)}
            className="flex w-full items-center justify-between gap-3 text-left"
          >
            <SubTitle help="Alíquota de IOF por dia de aplicação (dias 1 a 29). A partir do dia 30 não há IOF.">Tabela de IOF (resgates em menos de 30 dias)</SubTitle>
            <span className="text-muted [&_svg]:h-5 [&_svg]:w-5"><IconChevron open={showIof} /></span>
          </button>
          {showIof && (
            <div className="mt-3 grid grid-cols-3 gap-2 sm:grid-cols-5 lg:grid-cols-6">
              {form.iof.map((v, i) => (
                <div key={i}>
                  <div className="mb-0.5 text-[11px] text-muted">Dia {i + 1}</div>
                  <Cell label={`IOF no dia ${i + 1}`} value={v} suffix="%" error={err(`iof_table.${i}`)} onChange={(t) => edit({ iof: form.iof.map((x, j) => (j === i ? t : x)) })} />
                </div>
              ))}
            </div>
          )}
        </div>

        <div className="grid gap-4 sm:grid-cols-2">
          <Box label="Come-cotas de longo prazo" suffix="%" value={form.comeLongo} error={err("come_cotas_longo")} onChange={(v) => edit({ comeLongo: v })}
            hint="Cobrado em maio e novembro em fundos de longo prazo." />
          <Box label="Come-cotas de curto prazo" suffix="%" value={form.comeCurto} error={err("come_cotas_curto")} onChange={(v) => edit({ comeCurto: v })}
            hint="Cobrado em maio e novembro em fundos de curto prazo." />
          <Box label="IR de fundo de curto prazo, até 180 dias" suffix="%" value={form.irCurtoAte180} error={err("ir_fundo_curto_ate_180")} onChange={(v) => edit({ irCurtoAte180: v })}
            hint="Alíquota final para fundos de curto prazo resgatados em até 180 dias." />
          <Box label="IR de fundo de curto prazo, acima de 180 dias" suffix="%" value={form.irCurtoAcima180} error={err("ir_fundo_curto_acima_180")} onChange={(v) => edit({ irCurtoAcima180: v })}
            hint="Alíquota final para fundos de curto prazo após 180 dias." />
        </div>

        <div className="space-y-4">
          <SubTitle help="Marque os produtos que não pagam o imposto. Letras e certificados imobiliários e do agronegócio costumam ser isentos para pessoa física.">
            Isenções
          </SubTitle>
          <Exempt legend="Isentos de IR" value={form.irExempt} onChange={(v) => edit({ irExempt: v })} />
          <Exempt legend="Isentos de IOF" value={form.iofExempt} onChange={(v) => edit({ iofExempt: v })} />
        </div>
      </Group>

      <Group id="custos" title="Custos" localInvalid={localIn("custos")} errors={server}
        help="Taxas cobradas pela B3 para guardar seus títulos do Tesouro Direto.">
        <div className="grid gap-4 sm:grid-cols-2">
          <Box label="Custódia B3 (% ao ano)" suffix="% a.a." value={form.custodia} error={err("custodia_b3_aa")} onChange={(v) => edit({ custodia: v })}
            hint="Cobrada sobre o valor do Tesouro Direto guardado." />
          <Box label="Isenção de custódia do Tesouro Selic (R$)" suffix="R$" inputMode="numeric" value={form.isencaoSelic} error={err("tesouro_selic_isencao_custodia")}
            onChange={(v) => edit({ isencaoSelic: v })} hint="Até este valor em Tesouro Selic, não há cobrança de custódia." />
        </div>
      </Group>

      <Group id="projecoes" title="Projeções" localInvalid={localIn("projecoes")} errors={server}
        help="Produtos pós-fixados e atrelados à inflação dependem de uma previsão para Selic e IPCA. Escolha de onde vem essa previsão.">
        <div>
          <div role="radiogroup" aria-label="Fonte das projeções" className="inline-flex rounded-full border border-line bg-subtle p-0.5">
            {([["focus", "Focus"], ["manual", "Manual"]] as const).map(([id, label]) => (
              <button
                key={id}
                type="button"
                role="radio"
                aria-checked={form.mode === id}
                aria-label={label}
                onClick={() => setMode(id)}
                className={`rounded-full px-4 py-1.5 text-sm font-medium transition ${form.mode === id ? "bg-surface text-accent shadow-card" : "text-muted hover:text-ink"}`}
              >
                {label}
              </button>
            ))}
          </div>
          <p className="mt-2 text-xs text-muted">
            {form.mode === "focus"
              ? "Usa a média das previsões de mercado do Boletim Focus, do Banco Central, atualizada automaticamente."
              : "Você informa a Selic no fim de cada ano e o IPCA de cada ano. Anos além do último informado repetem o último valor."}
          </p>
        </div>

        {form.mode === "manual" && (
          <div>
            <div className="hidden grid-cols-[5rem_1fr_1fr_2.25rem] gap-2 px-1 pb-1 text-xs text-muted sm:grid">
              <span>Ano</span><span>Selic no fim do ano</span><span>IPCA no ano</span><span />
            </div>
            <div className="space-y-2">
              {form.rows.map((r, i) => {
                const ano = r.ano.trim() || `da linha ${i + 1}`;
                return (
                  <div key={i} className="grid grid-cols-[4.5rem_1fr_1fr_2.25rem] items-center gap-2 sm:grid-cols-[5rem_1fr_1fr_2.25rem]">
                    <Cell label={`Ano da linha ${i + 1}`} value={r.ano} inputMode="numeric" error={errors[`manual_selic_by_year.${i}`]} onChange={(v) => setRow(i, { ano: v })} />
                    <Cell label={`Selic no fim de ${ano} (%)`} value={r.selic} suffix="%" error={errors[`manual_selic_by_year.${i}.selic`]} onChange={(v) => setRow(i, { selic: v })} />
                    <Cell label={`IPCA em ${ano} (%)`} value={r.ipca} suffix="%" error={errors[`manual_ipca_by_year.${i}.ipca`]} onChange={(v) => setRow(i, { ipca: v })} />
                    <button
                      type="button"
                      aria-label={`Remover linha ${i + 1}`}
                      disabled={form.rows.length <= 1}
                      aria-describedby={form.rows.length === 1 ? "manual-min-note" : undefined}
                      title={form.rows.length <= 1 ? "Informe ao menos um ano" : undefined}
                      onClick={() => edit({ rows: form.rows.filter((_, j) => j !== i) })}
                      className="flex h-9 w-9 items-center justify-center rounded-full text-muted hover:bg-subtle hover:text-neg disabled:opacity-40 disabled:hover:bg-transparent disabled:hover:text-muted [&_svg]:h-4 [&_svg]:w-4"
                    >
                      <IconTrash />
                    </button>
                  </div>
                );
              })}
            </div>
            {form.rows.length === 1 && (
              <p id="manual-min-note" className="mt-2 text-xs text-muted">É preciso manter ao menos um ano na tabela.</p>
            )}
            {errors.manual_selic_by_year && <p className="mt-1.5 text-xs text-neg">{errors.manual_selic_by_year}</p>}
            {Object.entries(errors).filter(([p]) => /^manual_selic_by_year\.\d+$/.test(p)).map(([p, m]) => (
              <p key={p} className="mt-1.5 text-xs text-neg">Linha {Number(p.split(".")[1]) + 1}: {m}</p>
            ))}
            <button
              type="button"
              onClick={addRow}
              className="mt-3 inline-flex items-center gap-1.5 rounded-full border border-line px-3.5 py-1.5 text-sm font-medium text-accent hover:bg-subtle [&_svg]:h-4 [&_svg]:w-4"
            >
              <IconPlus /> Adicionar ano
            </button>
          </div>
        )}

        <Box label="Spread do CDI sobre a Selic (p.p.)" suffix="p.p." value={form.spread} error={err("spread_cdi_selic")} onChange={(v) => edit({ spread: v })} className="sm:max-w-xs"
          hint="Diferença entre a taxa Selic e o CDI, em pontos percentuais. Hoje o CDI costuma ficar 0,10 p.p. abaixo da Selic." />
      </Group>

      <Group id="dados" title="Dados" localInvalid={localIn("dados")} errors={server}
        help="De onde vêm as taxas e preços. Os dados ficam guardados por um tempo para a consulta ser rápida.">
        <Box label="Validade dos dados em cache (horas)" suffix="horas" inputMode="numeric" value={form.ttl} error={err("market_cache_ttl_hours")} onChange={(v) => edit({ ttl: v })}
          className="sm:max-w-xs" hint="Depois desse prazo, os dados são buscados de novo automaticamente." />
        <div>
          <SubTitle>Última atualização</SubTitle>
          {marketQ.isError && (
            <p role="alert" className="mt-2 rounded-xl border border-warn/30 bg-warn-bg px-3 py-2 text-xs text-warn">
              Não foi possível carregar o status dos dados de mercado.
            </p>
          )}
          <ul className="mt-2 divide-y divide-line rounded-xl border border-line">
            {FONTES.map((f) => {
              const at = market?.fetched_at[f.id];
              const msg = market?.errors[f.id];
              return (
                <li key={f.id} className="flex flex-wrap items-baseline justify-between gap-x-3 gap-y-0.5 px-3 py-2.5 text-sm">
                  <span className="font-medium">{f.label}</span>
                  <span className="text-muted">{at ? formatDateTime(at) : "ainda não atualizado"}</span>
                  {msg && <span className="basis-full text-xs text-warn">Falha na última tentativa: {msg}</span>}
                </li>
              );
            })}
          </ul>
          <button
            type="button"
            onClick={() => refresh.mutate()}
            disabled={refresh.isPending}
            className="mt-3 inline-flex items-center gap-2 rounded-full border border-line px-4 py-2 text-sm font-medium transition hover:text-accent disabled:opacity-60 [&_svg]:h-4 [&_svg]:w-4"
          >
            <IconRefresh spin={refresh.isPending} /> {refresh.isPending ? "Atualizando…" : "Atualizar agora"}
          </button>
        </div>
      </Group>

      <Group id="alertas" title="Alertas" localInvalid={localIn("alertas")} errors={server}
        help="Avisos mostrados nos cartões dos produtos.">
        <Box label="Limite do FGC por instituição (R$)" suffix="R$" inputMode="numeric" value={form.fgc} error={err("fgc_limite")} onChange={(v) => edit({ fgc: v })}
          className="sm:max-w-xs" hint="Você é avisado quando o valor aplicado em um emissor passa deste limite de proteção do FGC." />
      </Group>

      <Group id="prazos" title="Prazos mínimos" localInvalid={localIn("prazos")} errors={server}
        help="Prazo mínimo, em meses, que a regra do mercado exige de cada título isento. Produtos abaixo disso são recusados no cadastro.">
        <div className="grid gap-4 sm:grid-cols-3">
          {PRAZOS.map((p) => (
            <Box key={p.key} label={`${p.label} (meses)`} suffix="meses" inputMode="numeric" value={form.prazos[p.key]} error={err(p.field)}
              onChange={(v) => edit({ prazos: { ...form.prazos, [p.key]: v } })} />
          ))}
        </div>
      </Group>

      <Group id="ofertas" title="Ofertas" localInvalid={localIn("ofertas")} errors={server}
        help="Ofertas importadas de prints envelhecem: depois de alguns dias ganham um alerta e, mais tarde, saem do ranking até serem renovadas.">
        <div className="grid gap-4 sm:grid-cols-2">
          <Box label="Alertar após (dias)" suffix="dias" inputMode="numeric" value={form.ofertaAlerta} error={err("oferta_alerta_dias")}
            onChange={(v) => edit({ ofertaAlerta: v })} hint="Mostra o alerta Oferta antiga." />
          <Box label="Tirar do ranking após (dias)" suffix="dias" inputMode="numeric" value={form.ofertaExpira} error={err("oferta_expira_dias")}
            onChange={(v) => edit({ ofertaExpira: v })} hint="A oferta continua na lista, marcada como expirada." />
        </div>
      </Group>

      {dirty && (
        <div className="fixed inset-x-0 bottom-[calc(3.5rem+env(safe-area-inset-bottom))] z-10 flex items-center justify-between gap-3 border-t border-line bg-surface/95 px-4 py-3 backdrop-blur sm:sticky sm:bottom-4 sm:rounded-2xl sm:border sm:shadow-card">
          <p className="text-xs text-muted sm:text-sm"><span className="font-medium text-ink">Você tem alterações não salvas.</span></p>
          <button
            type="button"
            disabled={!canSave}
            onClick={() => save.mutate(built.settings)}
            className="shrink-0 whitespace-nowrap rounded-xl bg-accent px-5 py-2.5 text-sm font-semibold text-accent-fg transition hover:opacity-90 disabled:opacity-50"
          >
            {save.isPending ? "Salvando…" : "Salvar alterações"}
          </button>
        </div>
      )}

      <ConfirmReset open={confirmReset} pending={reset.isPending} onCancel={() => setConfirmReset(false)} onConfirm={() => reset.mutate()} />
    </div>
  );
}
