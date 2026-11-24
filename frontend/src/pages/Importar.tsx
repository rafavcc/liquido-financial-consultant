import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useEffect, useRef, useState, type DragEvent } from "react";
import { api, ApiError, printUrl } from "../api/client";
import type { ImportBatchView, ImportFailureView, ImportItemView, ProductData, ProductType } from "../api/types";
import { ProductForm } from "../components/ProductForm";
import { formatDateTime } from "../lib/format";

const POLL_MS = 3000;
const HISTORICO = 5;
const ACCEPT = "image/png,image/jpeg,image/webp";

const TIPOS_VALIDOS: ProductType[] = ["CDB", "LCI", "LCA", "LCD", "CRI", "CRA", "FUNDO_RF"];

/** Valores iniciais do formulário: o interpretado quando houver; senão só o que o raw traz sem conversão. */
function prefill(f: ImportFailureView): Partial<ProductData> {
  const interpretado = f.parcial.interpretado;
  if (interpretado && Object.keys(interpretado).length > 0) return interpretado;
  const raw = f.parcial.raw ?? {};
  const out: Partial<ProductData> = {};
  const tipo = typeof raw.tipo === "string" ? raw.tipo.toUpperCase() : "";
  if (TIPOS_VALIDOS.includes(tipo as ProductType)) out.tipo = tipo as ProductType;
  if (typeof raw.emissor === "string") out.emissor = raw.emissor;
  if (typeof raw.nome_exibido === "string") out.nome = raw.nome_exibido;
  return out;
}

const plural = (n: number, um: string, varios: string) => `${n} ${n === 1 ? um : varios}`;

function resultado(i: ImportItemView): string {
  const partes: string[] = [];
  if (i.criados) partes.push(plural(i.criados, "cadastrada", "cadastradas"));
  if (i.renovados) partes.push(plural(i.renovados, "renovada", "renovadas"));
  if (i.ignorados) partes.push(plural(i.ignorados, "ignorada", "ignoradas"));
  return `✓ ${partes.length ? partes.join(" · ") : "nenhuma oferta encontrada"}`;
}

function ItemRow({ item, onRetry, retrying }: { item: ImportItemView; onRetry: (id: string) => void; retrying: boolean }) {
  return (
    <li className="flex items-start gap-3 py-2">
      <a href={printUrl(item.print_id)} target="_blank" rel="noreferrer" className="shrink-0">
        <img src={printUrl(item.print_id)} alt="" loading="lazy" className="h-12 w-12 rounded-lg border border-line object-cover" />
      </a>
      <div className="min-w-0 flex-1 text-sm">
        <div className="truncate font-medium">{item.nome_arquivo}</div>
        <div className="mt-0.5 flex flex-wrap items-center gap-x-3 gap-y-1">
          {item.status === "NA_FILA" && <span className="text-muted">na fila</span>}
          {item.status === "LENDO" && <span className="text-accent">lendo…</span>}
          {item.status === "CONCLUIDO" && <span className="text-pos">{resultado(item)}</span>}
          {item.status === "CONCLUIDO" && item.falhas > 0 && (
            <span className="text-warn">⚠ {plural(item.falhas, "falha", "falhas")}</span>
          )}
          {item.status === "ERRO" && (
            <>
              <span className="text-neg">{item.erro ?? "Erro ao ler o print."}</span>
              <button
                type="button"
                disabled={retrying}
                onClick={() => onRetry(item.id)}
                className="rounded-lg border border-line px-2 py-0.5 text-xs font-medium hover:bg-subtle disabled:opacity-50"
              >
                Tentar de novo
              </button>
            </>
          )}
        </div>
      </div>
    </li>
  );
}

function FailureRow({ failure, onFix, onDiscard, busy }: { failure: ImportFailureView; onFix: () => void; onDiscard: () => void; busy: boolean }) {
  return (
    <li className="flex items-start gap-3 py-3">
      {failure.print_id && (
        <a href={printUrl(failure.print_id)} target="_blank" rel="noreferrer" className="shrink-0">
          <img src={printUrl(failure.print_id)} alt="" loading="lazy" className="h-16 w-16 rounded-lg border border-line object-cover" />
        </a>
      )}
      <div className="min-w-0 flex-1 text-sm">
        {failure.nome_arquivo && <div className="truncate font-medium">{failure.nome_arquivo}</div>}
        <ul className="mt-0.5 list-disc pl-5 text-warn">
          {failure.erros.map((e) => (
            <li key={e}>{e}</li>
          ))}
        </ul>
        <div className="mt-2 flex gap-2">
          <button type="button" onClick={onFix} className="rounded-lg bg-accent px-3 py-1 text-xs font-semibold text-accent-fg hover:opacity-90">
            Corrigir
          </button>
          <button type="button" disabled={busy} onClick={onDiscard} className="rounded-lg border border-line px-3 py-1 text-xs font-medium hover:bg-subtle disabled:opacity-50">
            Descartar
          </button>
        </div>
      </div>
    </li>
  );
}

function Batch({ batch, onRetry, retrying }: { batch: ImportBatchView; onRetry: (id: string) => void; retrying: boolean }) {
  const feitos = batch.itens.length - batch.pendentes;
  return (
    <section className="rounded-2xl border border-line bg-surface p-4 shadow-card">
      <div className="flex items-baseline justify-between gap-2">
        <h2 className="text-sm font-semibold">Lote de {formatDateTime(batch.criado_em)}</h2>
        <span className="num text-xs text-muted">
          {batch.pendentes > 0 ? `${feitos} de ${batch.itens.length} lidos` : `${plural(batch.itens.length, "print", "prints")}`}
        </span>
      </div>
      <ul className="mt-2 divide-y divide-line">
        {batch.itens.map((i) => (
          <ItemRow key={i.id} item={i} onRetry={onRetry} retrying={retrying} />
        ))}
      </ul>
    </section>
  );
}

export function Importar() {
  const qc = useQueryClient();
  const inputRef = useRef<HTMLInputElement>(null);
  const [recusados, setRecusados] = useState<string[]>([]);
  const [erro, setErro] = useState<string | null>(null);
  const [arrastando, setArrastando] = useState(false);

  const status = useQuery({ queryKey: ["imports", "status"], queryFn: api.imports.status });
  const lotes = useQuery({
    queryKey: ["imports", "list"],
    queryFn: api.imports.list,
    refetchInterval: (q) => (q.state.data?.some((b) => b.pendentes > 0) ? POLL_MS : false),
  });

  const falhas = useQuery({ queryKey: ["imports", "failures"], queryFn: () => api.imports.failures() });
  const [corrigindo, setCorrigindo] = useState<ImportFailureView | null>(null);
  const refreshAfterFailure = () => {
    for (const k of ["imports", "products", "simulate"]) void qc.invalidateQueries({ queryKey: [k] });
  };
  const discard = useMutation({
    mutationFn: api.imports.discard,
    onSuccess: () => { setErro(null); refreshAfterFailure(); },
    onError: (e) => setErro(e instanceof ApiError ? e.messages.join(" · ") : "Falha ao descartar."),
  });

  const pendentes = (lotes.data ?? []).reduce((n, b) => n + b.pendentes, 0);
  const anterior = useRef(0);
  useEffect(() => {
    if (anterior.current > 0 && pendentes === 0) {
      void qc.invalidateQueries({ queryKey: ["products"] });
      void qc.invalidateQueries({ queryKey: ["simulate"] });
    }
    anterior.current = pendentes;
  }, [pendentes, qc]);

  const upload = useMutation({
    mutationFn: api.imports.upload,
    onSuccess: (r) => {
      setErro(null);
      setRecusados(r.recusados);
      void qc.invalidateQueries({ queryKey: ["imports", "list"] });
    },
    onError: (e) => {
      setRecusados([]);
      setErro(e instanceof ApiError ? e.messages.join(" · ") : "Falha ao enviar os prints.");
    },
  });
  const retry = useMutation({
    mutationFn: api.imports.retry,
    onSuccess: () => void qc.invalidateQueries({ queryKey: ["imports", "list"] }),
    onError: (e) => setErro(e instanceof ApiError ? e.messages.join(" · ") : "Falha ao tentar de novo."),
  });

  const configurado = status.data?.configurado === true;
  const enviar = (files: FileList | File[] | null) => {
    const arr = files ? Array.from(files) : [];
    if (arr.length > 0 && configurado) upload.mutate(arr);
    if (inputRef.current) inputRef.current.value = "";
  };
  const onDrop = (e: DragEvent) => {
    e.preventDefault();
    setArrastando(false);
    enviar(e.dataTransfer.files);
  };

  return (
    <div className="space-y-4">
      <h1 className="text-xl font-semibold tracking-tight">Importar prints</h1>

      {status.isError && (
        <div role="alert" className="rounded-xl border border-line bg-subtle px-4 py-3 text-sm text-neg">
          Não foi possível verificar a importação. Tente recarregar a página.
        </div>
      )}
      {status.data && !status.data.configurado && (
        <div role="alert" className="rounded-xl border border-line bg-subtle px-4 py-3 text-sm">
          <strong>Importação não configurada</strong>
          <p className="mt-0.5 text-muted">Defina LLM_BASE_URL e CASA_LLM_MODEL no servidor para ler prints.</p>
        </div>
      )}
      {status.data?.configurado && status.data.alcancavel === false && (
        <div role="alert" className="rounded-xl border border-line bg-subtle px-4 py-3 text-sm text-warn">
          Servidor LLM indisponível no momento. Os prints entram na fila e são lidos quando ele voltar.
        </div>
      )}

      <label
        onDragOver={(e) => {
          e.preventDefault();
          setArrastando(true);
        }}
        onDragLeave={() => setArrastando(false)}
        onDrop={onDrop}
        className={`flex cursor-pointer flex-col items-center gap-1 rounded-2xl border-2 border-dashed px-4 py-8 text-center text-sm transition ${
          arrastando ? "border-accent bg-subtle" : "border-line"
        } ${configurado ? "" : "cursor-not-allowed opacity-60"}`}
      >
        <span className="font-medium">{upload.isPending ? "Enviando…" : "Escolher prints"}</span>
        <span className="text-muted">Toque para abrir a galeria ou arraste os arquivos aqui (PNG, JPEG ou WEBP, até 20 MB cada).</span>
        <input
          ref={inputRef}
          type="file"
          multiple
          accept={ACCEPT}
          aria-label="Escolher prints"
          disabled={!configurado || upload.isPending}
          onChange={(e) => enviar(e.target.files)}
          className="sr-only"
        />
      </label>

      {erro && (
        <p role="alert" className="text-sm text-neg">
          {erro}
        </p>
      )}
      {recusados.length > 0 && (
        <div role="status" className="rounded-xl border border-line bg-subtle px-4 py-3 text-sm">
          <div className="font-medium">Arquivos recusados</div>
          <ul className="mt-1 list-disc pl-5 text-muted">
            {recusados.map((r) => (
              <li key={r}>{r}</li>
            ))}
          </ul>
        </div>
      )}

      {falhas.data && falhas.data.length > 0 && (
        <section aria-label="Falhas" className="rounded-2xl border border-line bg-surface p-4 shadow-card">
          <h2 className="text-sm font-semibold">Falhas ({falhas.data.length})</h2>
          <p className="mt-0.5 text-xs text-muted">Ofertas que a leitura não conseguiu cadastrar. Corrija olhando o print ou descarte.</p>
          <ul className="mt-2 divide-y divide-line">
            {falhas.data.map((f) => (
              <FailureRow key={f.id} failure={f} busy={discard.isPending} onFix={() => setCorrigindo(f)} onDiscard={() => discard.mutate(f.id)} />
            ))}
          </ul>
        </section>
      )}

      {lotes.isError && <p className="text-sm text-neg">Não foi possível carregar os lotes.</p>}
      {lotes.data && lotes.data.length === 0 && <p className="py-8 text-center text-sm text-muted">Nenhum lote importado ainda.</p>}
      <div className="space-y-3">
        {(lotes.data ?? []).slice(0, HISTORICO).map((b) => (
          <Batch key={b.id} batch={b} onRetry={(id) => retry.mutate(id)} retrying={retry.isPending} />
        ))}
      </div>
      {corrigindo && (
        <ProductForm
          key={corrigindo.id}
          open
          initial={prefill(corrigindo)}
          printId={corrigindo.print_id ?? undefined}
          onSubmitOverride={async (p) => {
            const criado = await api.imports.resolve(corrigindo.id, p);
            void qc.invalidateQueries({ queryKey: ["imports"] });
            return criado;
          }}
          onOpenChange={(o) => !o && setCorrigindo(null)}
        />
      )}
    </div>
  );
}
