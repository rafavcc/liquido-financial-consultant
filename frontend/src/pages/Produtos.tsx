import * as Dialog from "@radix-ui/react-dialog";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useMemo, useState } from "react";
import { api, ApiError } from "../api/client";
import type { ProductData } from "../api/types";
import { IconChevron, IconCopy, IconEdit, IconPlus, IconTrash } from "../components/Icons";
import { ProductForm } from "../components/ProductForm";
import { formatBRL, formatDate } from "../lib/format";
import { indexLabel, resgateLabel, tipoLabel } from "../lib/labels";

const Chip = ({ children, className = "bg-subtle text-muted" }: { children: React.ReactNode; className?: string }) => (
  <span className={`inline-flex items-center rounded-md px-1.5 py-0.5 text-[11px] font-medium leading-4 ${className}`}>{children}</span>
);

const iconBtn =
  "flex h-8 w-8 items-center justify-center rounded-full text-muted transition hover:bg-subtle hover:text-ink [&_svg]:h-4 [&_svg]:w-4";

function Switch({ checked, label, disabled, onChange }: { checked: boolean; label: string; disabled?: boolean; onChange: (v: boolean) => void }) {
  return (
    <button
      type="button"
      role="switch"
      aria-checked={checked}
      aria-label={label}
      disabled={disabled}
      onClick={() => onChange(!checked)}
      className={`relative h-6 w-10 shrink-0 rounded-full transition disabled:opacity-60 ${checked ? "bg-accent" : "bg-line"}`}
    >
      <span
        className={`absolute left-0.5 top-0.5 h-5 w-5 rounded-full bg-surface shadow transition-transform ${checked ? "translate-x-4" : ""}`}
      />
    </button>
  );
}

function describe(p: ProductData): string {
  const dn = resgateLabel(p);
  return [
    p.plataforma,
    tipoLabel(p.tipo) + (dn ? ` ${dn}` : ""),
    indexLabel(p.indexador, p.taxa),
    p.data_vencimento ? `vence ${formatDate(p.data_vencimento)}` : null,
  ]
    .filter(Boolean)
    .join(" · ");
}

interface CardProps {
  p: ProductData;
  busy: boolean;
  onToggle: (p: ProductData, ativo: boolean) => void;
  onEdit: (p: ProductData) => void;
  onDuplicate: (p: ProductData) => void;
  onDelete: (p: ProductData) => void;
}

function ManualCard({ p, busy, onToggle, onEdit, onDuplicate, onDelete }: CardProps) {
  const minimo = Number(p.valor_minimo) > 0 ? `mín. ${formatBRL(p.valor_minimo)}` : null;
  return (
    <li className={`rounded-2xl border border-line bg-surface p-3 pl-4 shadow-card transition ${p.ativo ? "" : "opacity-70"}`}>
      <div className="flex items-start gap-3">
        <div className="min-w-0 flex-1">
          <h3 className="flex flex-wrap items-center gap-x-2 gap-y-1 text-[15px] font-semibold leading-tight">
            <span className="truncate">{p.nome}</span>
            {p.exemplo && <Chip className="bg-off-bg text-muted">Exemplo</Chip>}
            {!p.ativo && <Chip>Inativo</Chip>}
          </h3>
          <p className="mt-1 text-xs leading-5 text-muted">
            {describe(p)}
            {minimo && ` · ${minimo}`}
          </p>
        </div>
        <Switch checked={p.ativo} disabled={busy} label={`${p.ativo ? "Desativar" : "Ativar"} ${p.nome}`} onChange={(v) => onToggle(p, v)} />
      </div>
      <div className="-mb-0.5 mt-0.5 flex justify-end gap-0.5">
        <button type="button" className={iconBtn} aria-label={`Editar ${p.nome}`} onClick={() => onEdit(p)}><IconEdit /></button>
        <button type="button" className={iconBtn} aria-label={`Duplicar ${p.nome}`} disabled={busy} onClick={() => onDuplicate(p)}><IconCopy /></button>
        <button type="button" className={`${iconBtn} hover:!text-neg`} aria-label={`Excluir ${p.nome}`} onClick={() => onDelete(p)}><IconTrash /></button>
      </div>
    </li>
  );
}

function ConfirmDelete({ product, pending, onCancel, onConfirm }: { product: ProductData | null; pending: boolean; onCancel: () => void; onConfirm: () => void }) {
  return (
    <Dialog.Root open={product !== null} onOpenChange={(o) => !o && !pending && onCancel()}>
      <Dialog.Portal>
        <Dialog.Overlay className="detail-overlay fixed inset-0 z-40 bg-black/50" />
        <Dialog.Content className="detail-content fixed left-1/2 top-1/2 z-50 w-[calc(100%-2rem)] max-w-sm -translate-x-1/2 -translate-y-1/2 rounded-2xl border border-line bg-surface p-5 text-ink shadow-xl">
          <Dialog.Title className="text-base font-semibold">Excluir produto?</Dialog.Title>
          <Dialog.Description className="mt-1.5 text-sm text-muted">
            {product ? `"${product.nome}" será removido da sua lista e das comparações. Esta ação não pode ser desfeita.` : ""}
          </Dialog.Description>
          <div className="mt-5 flex justify-end gap-2">
            <Dialog.Close className="rounded-xl border border-line px-4 py-2 text-sm font-medium text-muted hover:text-ink">Cancelar</Dialog.Close>
            <button type="button" disabled={pending} onClick={onConfirm} className="rounded-xl bg-neg px-4 py-2 text-sm font-semibold text-white hover:opacity-90 disabled:opacity-60">
              {pending ? "Excluindo…" : "Excluir"}
            </button>
          </div>
        </Dialog.Content>
      </Dialog.Portal>
    </Dialog.Root>
  );
}

export function Produtos() {
  const qc = useQueryClient();
  const [form, setForm] = useState<{ product?: ProductData } | null>(null);
  const [toDelete, setToDelete] = useState<ProductData | null>(null);
  const [showTesouro, setShowTesouro] = useState(false);
  const [errors, setErrors] = useState<string[]>([]);

  const list = useQuery({ queryKey: ["products"], queryFn: api.products.list, retry: false });
  const tesouro = useQuery({ queryKey: ["tesouro"], queryFn: api.products.tesouro, retry: false });
  const market = useQuery({ queryKey: ["market"], queryFn: api.market, retry: false });

  const refetchAll = () => {
    void qc.invalidateQueries({ queryKey: ["products"] });
    void qc.invalidateQueries({ queryKey: ["simulate"] });
  };
  const onError = (e: unknown) => setErrors(e instanceof ApiError ? e.messages : ["Não foi possível concluir a operação."]);

  const toggle = useMutation({
    mutationFn: ({ p, ativo }: { p: ProductData; ativo: boolean }) => api.products.update(p.id, { ...p, ativo }),
    onSuccess: () => { setErrors([]); refetchAll(); },
    onError,
  });
  const duplicate = useMutation({
    mutationFn: (p: ProductData) => api.products.duplicate(p.id),
    onSuccess: () => { setErrors([]); refetchAll(); },
    onError,
  });
  const remove = useMutation({
    mutationFn: (p: ProductData) => api.products.remove(p.id),
    onSuccess: () => { setErrors([]); setToDelete(null); refetchAll(); },
    onError: (e) => { setToDelete(null); onError(e); },
  });

  const manuais = list.data ?? [];
  const plataformas = useMemo(() => [...new Set(manuais.map((p) => p.plataforma))].sort((a, b) => a.localeCompare(b, "pt-BR")), [manuais]);
  const busy = toggle.isPending || duplicate.isPending;
  const base = market.data?.tesouro_data_base;
  const loadError = list.error instanceof ApiError ? list.error.messages : list.error ? ["Não foi possível carregar os produtos."] : [];

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between gap-3">
        <h1 className="text-xl font-semibold tracking-tight">Produtos</h1>
        <button
          type="button"
          onClick={() => setForm({})}
          className="inline-flex items-center gap-1.5 rounded-full bg-accent px-4 py-2 text-sm font-semibold text-accent-fg transition hover:opacity-90 [&_svg]:h-4 [&_svg]:w-4"
        >
          <IconPlus /> Novo produto
        </button>
      </div>

      {[...errors, ...loadError].length > 0 && (
        <div role="alert" className="rounded-xl border border-neg/30 bg-neg-bg px-3 py-2 text-sm text-neg">
          {[...errors, ...loadError].map((m) => (
            <p key={m}>{m}</p>
          ))}
        </div>
      )}

      <section aria-label="Meus produtos">
        <h2 className="mb-3 flex items-center gap-2 text-base font-semibold">
          Meus produtos
          <span className="rounded-full bg-subtle px-2 py-0.5 text-xs font-medium text-muted">{manuais.length}</span>
        </h2>
        {list.isPending ? (
          <p className="py-8 text-center text-sm text-muted">Carregando…</p>
        ) : manuais.length === 0 && !list.isError ? (
          <div className="rounded-2xl border border-dashed border-line px-4 py-10 text-center">
            <p className="font-medium">Nenhum produto cadastrado</p>
            <p className="mx-auto mt-1 max-w-sm text-sm text-muted">
              Cadastre as ofertas que você viu na XP, no BTG ou em outra plataforma para compará-las com o Tesouro Direto.
            </p>
            <button type="button" onClick={() => setForm({})} className="mt-4 rounded-full bg-accent px-5 py-2 text-sm font-semibold text-accent-fg hover:opacity-90">
              Cadastrar primeiro produto
            </button>
          </div>
        ) : (
          <ul className="grid gap-3 md:grid-cols-2">
            {manuais.map((p) => (
              <ManualCard
                key={p.id}
                p={p}
                busy={busy}
                onToggle={(prod, ativo) => toggle.mutate({ p: prod, ativo })}
                onEdit={(prod) => setForm({ product: prod })}
                onDuplicate={(prod) => duplicate.mutate(prod)}
                onDelete={setToDelete}
              />
            ))}
          </ul>
        )}
      </section>

      <section aria-label="Tesouro Direto (automático)">
        <div className="mb-3 flex items-start justify-between gap-3">
          <div>
            <h2 className="flex items-center gap-2 text-base font-semibold">
              Tesouro Direto (automático)
              <span className="rounded-full bg-subtle px-2 py-0.5 text-xs font-medium text-muted">{tesouro.data?.length ?? 0}</span>
            </h2>
            <p className="mt-0.5 text-xs text-muted">
              Títulos e taxas atualizados sozinhos{base ? ` · dados de ${formatDate(base)}` : ""}. Somente leitura.
            </p>
          </div>
          <button
            type="button"
            aria-expanded={showTesouro}
            aria-label={showTesouro ? "Recolher Tesouro Direto" : "Mostrar Tesouro Direto"}
            onClick={() => setShowTesouro((s) => !s)}
            className="rounded-full p-1.5 text-muted hover:text-ink"
          >
            <IconChevron open={showTesouro} />
          </button>
        </div>
        {showTesouro &&
          (tesouro.isPending ? (
            <p className="py-6 text-center text-sm text-muted">Carregando…</p>
          ) : (tesouro.data ?? []).length === 0 ? (
            <p className="rounded-2xl border border-dashed border-line px-4 py-6 text-center text-sm text-muted">
              Nenhum título do Tesouro disponível no momento. Atualize os dados em Mercado.
            </p>
          ) : (
            <ul className="divide-y divide-line overflow-hidden rounded-2xl border border-line bg-surface shadow-card">
              {(tesouro.data ?? []).map((p) => (
                <li key={p.id} className="flex items-baseline justify-between gap-3 px-4 py-2.5">
                  <span className="min-w-0 truncate text-sm font-medium">{p.nome}</span>
                  <span className="shrink-0 text-xs text-muted">
                    {indexLabel(p.indexador, p.taxa)}
                    {p.data_vencimento && ` · ${formatDate(p.data_vencimento)}`}
                  </span>
                </li>
              ))}
            </ul>
          ))}
      </section>

      {form && (
        <ProductForm
          key={form.product?.id ?? "novo"}
          open
          product={form.product}
          plataformas={plataformas}
          onOpenChange={(o) => !o && setForm(null)}
        />
      )}
      <ConfirmDelete product={toDelete} pending={remove.isPending} onCancel={() => setToDelete(null)} onConfirm={() => toDelete && remove.mutate(toDelete)} />
    </div>
  );
}
